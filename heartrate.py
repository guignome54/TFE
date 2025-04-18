import bluetooth
import time
from micropython import const
from ubinascii import hexlify

_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)

# UUIDs
UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

HRS_SERVICE_UUID = bluetooth.UUID(0x180D)
HRS_MEASUREMENT_UUID = bluetooth.UUID(0x2A37)
print("hello")
target_mac = b'\xA0\x9E\x1A\x86\xEC\x33'  # Target MAC address

class BLECentral:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        self.conn_handle = None
        self.rx_handle = None
        self.tx_handle = None
        self.hrs_handle = None
        self.cccd_handles = {}
        
        # Service discovery tracking
        self.services_of_interest = {
            UART_SERVICE_UUID: {"found": False, "start_handle": 0, "end_handle": 0},
            HRS_SERVICE_UUID: {"found": False, "start_handle": 0, "end_handle": 0}
        }
        
        # State tracking
        self._scan_done = False
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._service_discovery_complete = False
        self._last_operation_time = 0
        
        print("Scanning...")
        self.ble.gap_scan(30000, 30000, 30000)

    def _irq(self, event, data):
        try:
            if event == _IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                print("Found:", hexlify(addr), "RSSI:", rssi)
                if addr == target_mac and not self._connecting:
                    print(target_mac)
                    print("Target found! Connecting...")
                    self._connecting = True
                    # Stop scanning before connecting
                    self.ble.gap_scan(None)
                    time.sleep_ms(200)  # Increased delay before connecting
                    self.ble.gap_connect(addr_type, addr)

            elif event == _IRQ_SCAN_DONE:
                self._scan_done = True
                print("Scan complete")

            elif event == _IRQ_PERIPHERAL_CONNECT:
                conn_handle, addr_type, addr = data
                print("Connected to:", hexlify(addr))
                self.conn_handle = conn_handle
                # Wait before discovering services
                self._last_operation_time = time.ticks_ms()
                print("Waiting before service discovery...")
                time.sleep_ms(500)  # Longer delay after connection
                self._start_service_discovery()

            elif event == _IRQ_PERIPHERAL_DISCONNECT:
                conn_handle, _, _ = data
                print("Disconnected")
                self._reset_state()

            elif event == _IRQ_GATTC_SERVICE_RESULT:
                conn_handle, start_handle, end_handle, uuid = data
                print(f"Service found: {uuid}")
                
                # Check if this is a service we're interested in
                if uuid in self.services_of_interest:
                    self.services_of_interest[uuid]["found"] = True
                    self.services_of_interest[uuid]["start_handle"] = start_handle
                    self.services_of_interest[uuid]["end_handle"] = end_handle
                    print(f"Service of interest found: {uuid}")

            elif event == _IRQ_GATTC_SERVICE_DONE:
                conn_handle, status = data
                print(f"Service discovery complete, status: {status}")
                self._discovering_services = False
                self._service_discovery_complete = True
                
                # Schedule characteristic discovery with delay
                print("Scheduling characteristic discovery...")
                self._last_operation_time = time.ticks_ms()
                time.sleep_ms(500)  # Wait before discovering characteristics
                self._discover_characteristics_for_services()

            elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
                conn_handle, def_handle, value_handle, properties, uuid = data
                print(f"Characteristic found: {uuid}, handle: {value_handle}")
                
                if uuid == UART_RX_CHAR_UUID:
                    self.rx_handle = value_handle
                    print("UART RX characteristic found, handle:", value_handle)
                
                elif uuid == UART_TX_CHAR_UUID:
                    self.tx_handle = value_handle
                    print("UART TX characteristic found, handle:", value_handle)
                    # Store CCCD handle
                    self.cccd_handles[self.tx_handle] = value_handle + 1
                
                elif uuid == HRS_MEASUREMENT_UUID:
                    self.hrs_handle = value_handle
                    print("Heart Rate characteristic found, handle:", value_handle)
                    # Store CCCD handle
                    self.cccd_handles[self.hrs_handle] = value_handle + 1
            
            elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
                conn_handle, status = data
                print(f"Characteristic discovery complete, status: {status}")
                self._discovering_chars = False
                
                # Schedule notification setup with delay
                print("Scheduling notification setup...")
                self._last_operation_time = time.ticks_ms()
                time.sleep_ms(1000)  # Longer delay before enabling notifications
                self._setup_notifications()

            elif event == _IRQ_GATTC_WRITE_DONE:
                conn_handle, value_handle, status = data
                print(f"Write completed, status: {status}")
                self._write_pending = False
                self._last_operation_time = time.ticks_ms()
                
                # Wait before continuing with any pending operations
                time.sleep_ms(300)
                
                # Check if we need to enable more notifications
                if self._service_discovery_complete:
                    self._continue_notification_setup()

            elif event == _IRQ_GATTC_NOTIFY:
                conn_handle, value_handle, notify_data = data
                if value_handle == self.hrs_handle:
                    # Parse heart rate data according to BLE spec
                    flags = notify_data[0]
                    if flags & 0x01:  # Check if value is in 16-bit format
                        bpm = int.from_bytes(notify_data[1:3], 'little')
                    else:
                        bpm = notify_data[1]
                    print(f"[Heart Rate] → {bpm} BPM")
                elif value_handle == self.tx_handle:
                    print(f"[UART] Received: {notify_data.decode('utf-8', 'replace')}")

        except Exception as e:
            print(f"Error in IRQ handler: {type(e).__name__}: {e}")
            # Don't reset state on error, just continue

    def _reset_state(self):
        """Reset connection state"""
        self.conn_handle = None
        self.rx_handle = None
        self.tx_handle = None
        self.hrs_handle = None
        self._connecting = False
        self._discovering_services = False
        self._discovering_chars = False
        self._write_pending = False
        self._service_discovery_complete = False
        self.cccd_handles = {}
        
        # Reset service tracking
        for service in self.services_of_interest:
            self.services_of_interest[service]["found"] = False
            self.services_of_interest[service]["start_handle"] = 0
            self.services_of_interest[service]["end_handle"] = 0

    def _start_service_discovery(self):
        """Start discovering services"""
        if not self.conn_handle or self._discovering_services:
            print("Cannot discover services: not connected or already discovering")
            return
            
        print("Starting service discovery...")
        try:
            self._discovering_services = True
            self.ble.gattc_discover_services(self.conn_handle)
        except OSError as e:
            print(f"Error starting service discovery: {e}")
            self._discovering_services = False
            
            # Retry after a delay
            print("Retrying service discovery in 1 second...")
            time.sleep_ms(1000)
            self._start_service_discovery()

    def _discover_characteristics_for_services(self):
        """Discover characteristics for services of interest"""
        if not self.conn_handle or self._discovering_chars:
            print("Cannot discover characteristics: not connected or already discovering")
            return
            
        # Check if we found any services of interest
        services_to_discover = [s for s, info in self.services_of_interest.items() if info["found"]]
        
        if not services_to_discover:
            print("No services of interest found")
            return
            
        # Start with the first service
        self._discover_characteristics_for_service(services_to_discover[0])

    def _discover_characteristics_for_service(self, service_uuid):
        """Discover characteristics for a specific service"""
        if not self.conn_handle:
            return
            
        service_info = self.services_of_interest[service_uuid]
        if not service_info["found"]:
            return
            
        start_handle = service_info["start_handle"]
        end_handle = service_info["end_handle"]
        
        print(f"Discovering characteristics for {service_uuid}...")
        try:
            self._discovering_chars = True
            self.ble.gattc_discover_characteristics(
                self.conn_handle, start_handle, end_handle
            )
        except OSError as e:
            print(f"Error discovering characteristics: {e}")
            self._discovering_chars = False
            
            # Retry after a delay
            print("Retrying characteristic discovery in 1 second...")
            time.sleep_ms(1000)
            self._discover_characteristics_for_service(service_uuid)

    def _setup_notifications(self):
        """Set up notifications for discovered characteristics"""
        if not self.conn_handle or self._write_pending:
            print("Cannot setup notifications: not connected or write pending")
            return
            
        # Start with heart rate if available
        if self.hrs_handle and self.hrs_handle in self.cccd_handles:
            self._enable_notifications_for_characteristic(self.hrs_handle)
        else:
            # Try UART if available
            if self.tx_handle and self.tx_handle in self.cccd_handles:
                self._enable_notifications_for_characteristic(self.tx_handle)

    def _continue_notification_setup(self):
        """Continue setting up notifications after a previous one completes"""
        if not self.conn_handle or self._write_pending:
            return
            
        # If we've already set up heart rate, try UART
        if self.hrs_handle and self.tx_handle and self.tx_handle in self.cccd_handles:
            self._enable_notifications_for_characteristic(self.tx_handle)

    def _enable_notifications_for_characteristic(self, char_handle):
        """Enable notifications for a specific characteristic"""
        if not self.conn_handle or char_handle not in self.cccd_handles or self._write_pending:
            return
            
        cccd_handle = self.cccd_handles[char_handle]
        char_name = "UART TX" if char_handle == self.tx_handle else "Heart Rate" if char_handle == self.hrs_handle else "Unknown"
        
        print(f"Enabling {char_name} notifications (CCCD handle: {cccd_handle})...")
        try:
            self._write_pending = True
            self.ble.gattc_write(self.conn_handle, cccd_handle, b'\x01\x00', 1)
        except OSError as e:
            print(f"Failed to enable {char_name} notifications: {e}")
            self._write_pending = False
            
            # Retry after a delay
            print(f"Retrying {char_name} notification setup in 1 second...")
            time.sleep_ms(1000)
            self._enable_notifications_for_characteristic(char_handle)

    def send_uart(self, text):
        """Send data over UART service"""
        if not self.conn_handle or not self.rx_handle:
            print("Not connected or RX handle missing")
            return False
            
        # Don't send if another write is pending
        if self._write_pending:
            print("Write operation already pending, try again later")
            return False
            
        try:
            self._write_pending = True
            self.ble.gattc_write(self.conn_handle, self.rx_handle, text.encode(), 1)
            print(f"Sent: {text}")
            return True
        except OSError as e:
            print(f"Failed to send UART data: {e}")
            self._write_pending = False
            return False


# Test
central = BLECentral()

# Wait to connect before sending - using a better approach with timeout
print("Waiting for connection and service discovery...")
timeout = 60  # 60 seconds timeout
start_time = time.time()

while time.time() - start_time < timeout:
    if central.conn_handle and central.rx_handle:
        print("Connected and ready, sending test message...")
        # Wait a bit more to ensure all setup is complete
        time.sleep(2)
        central.send_uart("Hello from Central 👋")
        break
    time.sleep(1)
else:
    print("Failed to connect or discover services within timeout")

# Keep the script running to receive notifications
print("Listening for notifications (press Ctrl+C to exit)...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")