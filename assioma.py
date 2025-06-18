import bluetooth
from micropython import const
import time
import struct

# BLE Event IRQs
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)

# Adresse MAC cible de la pédale Assioma (modifiez avec l'adresse de votre pédale)
target_mac = b'\xE9\xB5\x4A\x31\x63\xB5'

# UUIDs des services et caractéristiques
CPM_SERVICE_UUID = bluetooth.UUID(0x1818)  # Cycling Power Service
CPM_MEASUREMENT_UUID = bluetooth.UUID(0x2A63)  # Cycling Power Measurement
BATTERY_SERVICE_UUID = bluetooth.UUID(0x180F)  # Battery Service
BATTERY_LEVEL_UUID = bluetooth.UUID(0x2A19)  # Battery Level

# Variables globales
ble_connected = False
current_power = 0
battery_level = 0

class AssiomaBLEClient:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        # Handles pour la connexion et les caractéristiques
        self.conn_handle = None
        self.cpm_measurement_handle = None
        self.battery_level_handle = None
        self.cccd_handles = {}
        
        # Variables d'état
        self._scan_done = False
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._read_pending = False
        
        # Données
        self.last_power = 0
        self.last_battery = 0
        self.scan_started = False
        
    def start_scan(self):
        """Démarre le scan pour trouver la pédale Assioma"""
        if not self.scan_started:
            self.ble.gap_scan(10000, 30000, 30000)
            self.scan_started = True
            
    def stop_scan(self):
        """Arrête le scan BLE en cours"""
        if self.scan_started:
            self.ble.gap_scan(None)
            self.scan_started = False
            self._scan_done = True

    def _irq(self, event, data):
        try:
            if event == _IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                if addr == target_mac and not self._connecting:
                    print(f"Pédale Assioma trouvée! RSSI: {rssi} dBm. Connexion en cours...")
                    self._connecting = True
                    # Arrêter le scan avant de se connecter
                    self.ble.gap_scan(None)
                    self.scan_started = False
                    time.sleep_ms(200)
                    self.ble.gap_connect(addr_type, addr)

            elif event == _IRQ_SCAN_DONE:
                self._scan_done = True
                self.scan_started = False


            elif event == _IRQ_PERIPHERAL_CONNECT:
                conn_handle, addr_type, addr = data
                global ble_connected
                ble_connected = True
                self.conn_handle = conn_handle
                # Découverte des services après délai
                time.sleep_ms(500)
                self._start_service_discovery()

            elif event == _IRQ_PERIPHERAL_DISCONNECT:
                conn_handle, _, _ = data
                global ble_connected
                ble_connected = False
                self._reset_state()

            elif event == _IRQ_GATTC_SERVICE_RESULT:
                conn_handle, start_handle, end_handle, uuid = data
                if uuid == CPM_SERVICE_UUID:
                    self._cpm_service_start_handle = start_handle
                    self._cpm_service_end_handle = end_handle
                elif uuid == BATTERY_SERVICE_UUID:
                    self._battery_service_start_handle = start_handle
                    self._battery_service_end_handle = end_handle

            elif event == _IRQ_GATTC_SERVICE_DONE:
                conn_handle, status = data
                self._discovering_services = False
                time.sleep_ms(500)
                # Découvrir les caractéristiques du service de puissance en premier
                self._discover_characteristics(self._cpm_service_start_handle, self._cpm_service_end_handle)

            elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
                conn_handle, def_handle, value_handle, properties, uuid = data
                if uuid == CPM_MEASUREMENT_UUID:
                    self.cpm_measurement_handle = value_handle
                    # Stocker le handle CCCD (pour les notifications)
                    self.cccd_handles[self.cpm_measurement_handle] = value_handle + 1
                elif uuid == BATTERY_LEVEL_UUID:
                    self.battery_level_handle = value_handle
                    # Stocker le handle CCCD (pour les notifications optionnelles)
                    self.cccd_handles[self.battery_level_handle] = value_handle + 1
            
            elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
                conn_handle, status = data
                self._discovering_chars = False
                
                # S'il nous reste à découvrir les caractéristiques de batterie
                if hasattr(self, '_battery_service_start_handle') and not self.battery_level_handle:
                    time.sleep_ms(500)
                    self._discover_characteristics(self._battery_service_start_handle, self._battery_service_end_handle)
                else:
                    # Configuration des notifications pour la puissance
                    time.sleep_ms(500)
                    self._setup_notifications()
                    
                    # Lecture initiale du niveau de batterie
                    if self.battery_level_handle:
                        time.sleep_ms(500)
                        self.read_battery_level()

            elif event == _IRQ_GATTC_READ_RESULT:
                conn_handle, value_handle, data = data
                if value_handle == self.battery_level_handle:
                    self._read_pending = False
                    battery = struct.unpack("<B", data)[0]
                    self.last_battery = battery
                    global battery_level
                    battery_level = battery
                    print(f"Niveau de batterie: {battery}%")

            elif event == _IRQ_GATTC_WRITE_DONE:
                conn_handle, value_handle, status = data
                self._write_pending = False

            elif event == _IRQ_GATTC_NOTIFY:
                conn_handle, value_handle, notify_data = data
                if value_handle == self.cpm_measurement_handle:
                    self._parse_power_measurement(notify_data)
                elif value_handle == self.battery_level_handle:
                    # Si on reçoit des notifications de batterie
                    battery = struct.unpack("<B", notify_data)[0]
                    self.last_battery = battery
                    global battery_level
                    battery_level = battery

        except Exception as e:
            print(f"Erreur BLE: {e}")

    def _parse_power_measurement(self, data):
        """Analyse les données de mesure de puissance"""
        try:
            if len(data) < 4:
                return
                
            # Les 2 premiers octets sont les flags
            flags = struct.unpack("<H", data[0:2])[0]
            
            # Puissance instantanée (toujours présente)
            power = struct.unpack("<h", data[2:4])[0]
            
            # Mettre à jour la puissance
            self.last_power = power
            global current_power
            current_power = power
            
        except Exception as e:
            print(f"Erreur données puissance: {e}")

    def _reset_state(self):
        """Réinitialise l'état de connexion"""
        self.conn_handle = None
        self.cpm_measurement_handle = None
        self.battery_level_handle = None
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._read_pending = False
        self.cccd_handles = {}
        self.scan_started = False

    def _start_service_discovery(self):
        """Démarre la découverte des services"""
        if not self.conn_handle or self._discovering_services:
            return
            
        try:
            self._discovering_services = True
            self.ble.gattc_discover_services(self.conn_handle)
        except Exception as e:
            print(f"Erreur découverte services: {e}")
            self._discovering_services = False

    def _discover_characteristics(self, start_handle, end_handle):
        """Découvre les caractéristiques d'un service"""
        if not self.conn_handle or self._discovering_chars:
            return
            
        try:
            self._discovering_chars = True
            self.ble.gattc_discover_characteristics(self.conn_handle, start_handle, end_handle)
        except Exception as e:
            print(f"Erreur découverte caractéristiques: {e}")
            self._discovering_chars = False

    def _setup_notifications(self):
        """Configure les notifications pour la mesure de puissance"""
        if not self.conn_handle or self._write_pending:
            return
            
        # Activer les notifications pour la mesure de puissance
        if self.cpm_measurement_handle and self.cpm_measurement_handle in self.cccd_handles:
            cccd_handle = self.cccd_handles[self.cpm_measurement_handle]
            try:
                self._write_pending = True
                self.ble.gattc_write(self.conn_handle, cccd_handle, b'\x01\x00', 1)
            except Exception as e:
                print(f"Erreur activation notifications: {e}")
                self._write_pending = False

    def read_battery_level(self):
        """Lit le niveau de batterie actuel"""
        if not self.conn_handle or not self.battery_level_handle or self._read_pending:
            return
            
        try:
            self._read_pending = True
            self.ble.gattc_read(self.conn_handle, self.battery_level_handle)
        except Exception as e:
            print(f"Erreur lecture batterie: {e}")
            self._read_pending = False

    def get_current_power(self):
        """Renvoie la dernière valeur de puissance reçue"""
        return self.last_power
    
    def get_battery_level(self):
        """Renvoie le dernier niveau de batterie lu"""
        return self.last_battery

    def disconnect(self):
        """Déconnexion de la pédale"""
        if self.conn_handle is not None:
            try:
                self.ble.gap_disconnect(self.conn_handle)
            except Exception as e:
                print(f"Erreur déconnexion: {e}")