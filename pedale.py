import bluetooth
import time
import struct
from micropython import const
from ubinascii import hexlify

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

# Cycling Power UUIDs d'après l'image
CPM_SERVICE_UUID = bluetooth.UUID(0x1818)  # Cycling Power Service
CPM_MEASUREMENT_UUID = bluetooth.UUID(0x2A63)  # Cycling Power Measurement
CPM_FEATURE_UUID = bluetooth.UUID(0x2A65)  # Cycling Power Feature
CPM_CONTROL_POINT_UUID = bluetooth.UUID(0x2A66)  # Cycling Power Control Point
CPM_SENSOR_LOCATION_UUID = bluetooth.UUID(0x2A5D)  # Sensor Location

# Adresse MAC de la pédale Assioma-MX2
target_mac = b'\xE9\xB5\x4A\x31\x63\xB5'  # E9:B5:4A:31:63:B5

class AssiomaBLEClient:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        # Handles pour la connexion et les caractéristiques
        self.conn_handle = None
        self.cpm_measurement_handle = None
        self.cpm_feature_handle = None
        self.cpm_control_point_handle = None
        self.cpm_sensor_location_handle = None
        self.cccd_handles = {}
        
        # Suivi des services
        self.services_of_interest = {
            CPM_SERVICE_UUID: {"found": False, "start_handle": 0, "end_handle": 0}
        }
        
        # Variables d'état
        self._scan_done = False
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._service_discovery_complete = False
        self._last_operation_time = 0
        
        # Données de puissance
        self.last_power = 0
        self.last_cadence = 0
        self.total_revolutions = 0
        self.last_event_time = 0
        
        print("Démarrage du scan pour Assioma-MX2...")
        self.ble.gap_scan(30000, 30000, 30000)

    def _irq(self, event, data):
        try:
            if event == _IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                addr_str = hexlify(addr)
                print("Appareil trouvé:", addr_str, "RSSI:", rssi)
                if addr == target_mac and not self._connecting:
                    print("Pédale Assioma-MX2 trouvée! Connexion en cours...")
                    self._connecting = True
                    # Arrêter le scan avant de se connecter
                    self.ble.gap_scan(None)
                    time.sleep_ms(200)
                    self.ble.gap_connect(addr_type, addr)

            elif event == _IRQ_SCAN_DONE:
                self._scan_done = True
                print("Scan terminé")

            elif event == _IRQ_PERIPHERAL_CONNECT:
                conn_handle, addr_type, addr = data
                print("Connecté à:", hexlify(addr))
                self.conn_handle = conn_handle
                # Attendre avant de découvrir les services
                self._last_operation_time = time.ticks_ms()
                print("Attente avant découverte des services...")
                time.sleep_ms(500)
                self._start_service_discovery()

            elif event == _IRQ_PERIPHERAL_DISCONNECT:
                conn_handle, _, _ = data
                print("Déconnecté")
                self._reset_state()

            elif event == _IRQ_GATTC_SERVICE_RESULT:
                conn_handle, start_handle, end_handle, uuid = data
                print(f"Service trouvé: {uuid}")
                
                # Vérifier si c'est un service qui nous intéresse
                if uuid == CPM_SERVICE_UUID:
                    self.services_of_interest[uuid]["found"] = True
                    self.services_of_interest[uuid]["start_handle"] = start_handle
                    self.services_of_interest[uuid]["end_handle"] = end_handle
                    print(f"Service Cycling Power trouvé")

            elif event == _IRQ_GATTC_SERVICE_DONE:
                conn_handle, status = data
                print(f"Découverte des services terminée, statut: {status}")
                self._discovering_services = False
                self._service_discovery_complete = True
                
                # Programmer la découverte des caractéristiques avec délai
                print("Programmation de la découverte des caractéristiques...")
                self._last_operation_time = time.ticks_ms()
                time.sleep_ms(500)
                self._discover_characteristics_for_services()

            elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
                conn_handle, def_handle, value_handle, properties, uuid = data
                print(f"Caractéristique trouvée: {uuid}, handle: {value_handle}, propriétés: {properties}")
                
                if uuid == CPM_MEASUREMENT_UUID:
                    self.cpm_measurement_handle = value_handle
                    print("Caractéristique de mesure de puissance trouvée")
                    # Stocker le handle CCCD (pour les notifications)
                    self.cccd_handles[self.cpm_measurement_handle] = value_handle + 1
                
                elif uuid == CPM_FEATURE_UUID:
                    self.cpm_feature_handle = value_handle
                    print("Caractéristique de fonctionnalités de puissance trouvée")
                
                elif uuid == CPM_CONTROL_POINT_UUID:
                    self.cpm_control_point_handle = value_handle
                    print("Point de contrôle de puissance trouvé")
                    # Stocker le handle CCCD pour les indications
                    self.cccd_handles[self.cpm_control_point_handle] = value_handle + 1
                
                elif uuid == CPM_SENSOR_LOCATION_UUID:
                    self.cpm_sensor_location_handle = value_handle
                    print("Position du capteur trouvée")
            
            elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
                conn_handle, status = data
                print(f"Découverte des caractéristiques terminée, statut: {status}")
                self._discovering_chars = False
                
                # Programmer la configuration des notifications avec délai
                print("Programmation de la configuration des notifications...")
                self._last_operation_time = time.ticks_ms()
                time.sleep_ms(1000)
                self._setup_notifications()

            elif event == _IRQ_GATTC_READ_RESULT:
                conn_handle, value_handle, char_data = data
                print(f"Données lues du handle {value_handle}: {char_data}")

                if value_handle == self.cpm_sensor_location_handle:
                    # La position du capteur est un seul octet selon la spec
                    location = struct.unpack("<B", char_data)[0]
                    location_str = self._sensor_location_to_str(location)
                    print(f"📍 Position du capteur: {location_str} (code: {location})")

            elif event == _IRQ_GATTC_WRITE_DONE:
                conn_handle, value_handle, status = data
                print(f"Écriture terminée, statut: {status}")
                self._write_pending = False
                self._last_operation_time = time.ticks_ms()
                
                # Attendre avant de continuer avec d'autres opérations
                time.sleep_ms(300)
                
                # Vérifier si nous devons lire certaines caractéristiques
                if self._service_discovery_complete and not self._write_pending:
                    self._read_characteristics()

            elif event == _IRQ_GATTC_NOTIFY:
                conn_handle, value_handle, notify_data = data
                if value_handle == self.cpm_measurement_handle:
                    self._parse_power_measurement(notify_data)

        except Exception as e:
            print(f"Erreur dans le gestionnaire IRQ: {type(e).__name__}: {e}")

    def _parse_power_measurement(self, data):
        """Analyse les données de mesure de puissance selon la spécification BLE Cycling Power"""
        try:
            if len(data) < 4:
                print("Données de puissance trop courtes")
                return
                
            # Les 2 premiers octets sont les flags
            flags = struct.unpack("<H", data[0:2])[0]
            
            # Position des données en fonction des flags
            index = 2
            
            # Puissance instantanée (toujours présente, int16, watts)
            power = struct.unpack("<h", data[index:index+2])[0]
            index += 2
            
            # Afficher la puissance
            self.last_power = power
            print(f"[Puissance] → {power} Watts")
            
            # Si les données de cadence sont présentes (bit 5 des flags)
            if flags & (1 << 5):
                # On pourrait extraire la cadence ici si nécessaire
                # Pour simplifier, on ne le fait pas dans cet exemple
                pass
                
        except Exception as e:
            print(f"Erreur lors de l'analyse des données de puissance: {e}")

    def _reset_state(self):
        """Réinitialise l'état de connexion"""
        self.conn_handle = None
        self.cpm_measurement_handle = None
        self.cpm_feature_handle = None
        self.cpm_control_point_handle = None
        self.cpm_sensor_location_handle = None
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._service_discovery_complete = False
        self.cccd_handles = {}
        
        # Réinitialiser le suivi des services
        for service in self.services_of_interest:
            self.services_of_interest[service]["found"] = False
            self.services_of_interest[service]["start_handle"] = 0
            self.services_of_interest[service]["end_handle"] = 0

    def _start_service_discovery(self):
        """Démarre la découverte des services"""
        if not self.conn_handle or self._discovering_services:
            print("Impossible de découvrir les services: non connecté ou découverte déjà en cours")
            return
            
        print("Démarrage de la découverte des services...")
        try:
            self._discovering_services = True
            self.ble.gattc_discover_services(self.conn_handle)
        except OSError as e:
            print(f"Erreur lors du démarrage de la découverte des services: {e}")
            self._discovering_services = False
            
            # Réessayer après un délai
            print("Nouvelle tentative de découverte des services dans 1 seconde...")
            time.sleep_ms(1000)
            self._start_service_discovery()

    def _discover_characteristics_for_services(self):
        """Découvre les caractéristiques pour les services d'intérêt"""
        if not self.conn_handle or self._discovering_chars:
            print("Impossible de découvrir les caractéristiques: non connecté ou découverte déjà en cours")
            return
            
        # Vérifier si nous avons trouvé des services d'intérêt
        services_to_discover = [s for s, info in self.services_of_interest.items() if info["found"]]
        
        if not services_to_discover:
            print("Aucun service d'intérêt trouvé")
            return
            
        # Commencer par le premier service
        self._discover_characteristics_for_service(services_to_discover[0])

    def _discover_characteristics_for_service(self, service_uuid):
        """Découvre les caractéristiques pour un service spécifique"""
        if not self.conn_handle:
            return
            
        service_info = self.services_of_interest[service_uuid]
        if not service_info["found"]:
            return
            
        start_handle = service_info["start_handle"]
        end_handle = service_info["end_handle"]
        
        print(f"Découverte des caractéristiques pour {service_uuid}...")
        try:
            self._discovering_chars = True
            self.ble.gattc_discover_characteristics(
                self.conn_handle, start_handle, end_handle
            )
        except OSError as e:
            print(f"Erreur lors de la découverte des caractéristiques: {e}")
            self._discovering_chars = False
            
            # Réessayer après un délai
            print("Nouvelle tentative de découverte des caractéristiques dans 1 seconde...")
            time.sleep_ms(1000)
            self._discover_characteristics_for_service(service_uuid)

    def _setup_notifications(self):
        """Configure les notifications pour les caractéristiques découvertes"""
        if not self.conn_handle or self._write_pending:
            print("Impossible de configurer les notifications: non connecté ou écriture en cours")
            return
            
        # Activer les notifications pour la mesure de puissance
        if self.cpm_measurement_handle and self.cpm_measurement_handle in self.cccd_handles:
            self._enable_notifications_for_characteristic(self.cpm_measurement_handle)

    def _enable_notifications_for_characteristic(self, char_handle):
        """Active les notifications pour une caractéristique spécifique"""
        if not self.conn_handle or char_handle not in self.cccd_handles or self._write_pending:
            return
            
        cccd_handle = self.cccd_handles[char_handle]
        char_name = "Mesure de Puissance" if char_handle == self.cpm_measurement_handle else "Inconnue"
        
        print(f"Activation des notifications pour {char_name} (handle CCCD: {cccd_handle})...")
        try:
            self._write_pending = True
            self.ble.gattc_write(self.conn_handle, cccd_handle, b'\x01\x00', 1)
        except OSError as e:
            print(f"Échec de l'activation des notifications pour {char_name}: {e}")
            self._write_pending = False
            
            # Réessayer après un délai
            print(f"Nouvelle tentative d'activation des notifications pour {char_name} dans 1 seconde...")
            time.sleep_ms(1000)
            self._enable_notifications_for_characteristic(char_handle)

    def _read_characteristics(self):
        """Lit les caractéristiques qui ont des propriétés READ"""
        # Lire les fonctionnalités de puissance
        if self.cpm_feature_handle:
            try:
                print("Lecture des fonctionnalités de puissance...")
                self.ble.gattc_read(self.conn_handle, self.cpm_feature_handle)
            except OSError as e:
                print(f"Échec de la lecture des fonctionnalités de puissance: {e}")
        
        # Lire la position du capteur
        if self.cpm_sensor_location_handle:
            try:
                print("Lecture de la position du capteur...")
                self.ble.gattc_read(self.conn_handle, self.cpm_sensor_location_handle)
            except OSError as e:
                print(f"Échec de la lecture de la position du capteur: {e}")

    def get_current_power(self):
        """Renvoie la dernière valeur de puissance reçue"""
        return self.last_power

# Test du client BLE
assioma_client = AssiomaBLEClient()

# Attendre la connexion et la configuration
print("Attente de la connexion et de la découverte des services...")
timeout = 60  # timeout de 60 secondes
start_time = time.time()

while time.time() - start_time < timeout:
    if assioma_client.conn_handle and assioma_client.cpm_measurement_handle:
        print("Connecté et prêt à recevoir les données de puissance.")
        break
    time.sleep(1)
else:
    print("Échec de la connexion ou de la découverte des services dans le délai imparti")

# Maintenir le script en exécution pour recevoir les notifications
print("Écoute des notifications de puissance (appuyez sur Ctrl+C pour quitter)...")
try:
    while True:
        if assioma_client.conn_handle:
            current_power = assioma_client.get_current_power()
            if current_power > 0:
                print(f"Puissance actuelle: {current_power} W")
        time.sleep(1)
except KeyboardInterrupt:
    print("Sortie...")