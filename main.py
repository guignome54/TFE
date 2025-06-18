from machine import Pin, Timer, I2C, PWM, ADC, WDT
import neopixel
import time
from ssd1306 import SSD1306_I2C

time.sleep(2)

import bluetooth
from micropython import const
from ubinascii import hexlify
import assioma
import vitesse


# ----- NeoPixel Configuration -----
BROCHE_NEO = 14
NOMBRE_NEO = 52
np = neopixel.NeoPixel(Pin(15), NOMBRE_NEO)

# Adresse MAC de la pédale Assioma-MX2
target_mac = b'\xE9\xB5\x4A\x31\x63\xB5'  # E9:B5:4A:31:63:B5

COULEUR_ALLUME = (255, 60, 0)
COULEUR_ETEINT = (0, 0, 0)
COULEUR_ROUGE = (120, 0, 0)

INDICE_DEBUT_GAUCHE = 19
INDICE_FIN_GAUCHE = 25
INDICE_DEBUT_DROIT = 6
INDICE_FIN_DROIT = 0

# ----- Boutons -----
BROCHE_BOUTON_GAUCHE = 2
BROCHE_BOUTON_DROIT = 0
BROCHE_FREIN = 7
BROCHE_FEUX_DETRESSE = 4
BROCHE_PAGE = 8
BROCHE_ARRIERE = 6
BROCHE_REED = 21
BROCHE_PHARE = 11
BROCHE_CHRONO = 13
bouton_gauche = Pin(BROCHE_BOUTON_GAUCHE, Pin.IN, Pin.PULL_UP)
bouton_droit = Pin(BROCHE_BOUTON_DROIT, Pin.IN, Pin.PULL_UP)
frein = Pin(BROCHE_FREIN, Pin.IN, Pin.PULL_UP)
bouton_feux_detresse = Pin(BROCHE_FEUX_DETRESSE, Pin.IN, Pin.PULL_UP)
bouton_page = Pin(BROCHE_PAGE, Pin.IN, Pin.PULL_UP)
bouton_arriere = Pin(BROCHE_ARRIERE, Pin.IN, Pin.PULL_UP)
bouton_reed = Pin(BROCHE_REED, Pin.IN, Pin.PULL_UP)
bouton_phare = Pin(BROCHE_PHARE, Pin.IN, Pin.PULL_UP)
bouton_chrono = Pin(BROCHE_CHRONO, Pin.IN, Pin.PULL_UP)

pwm = PWM(Pin(18), freq=144)
# ----- LCD (I2C) -----
SDA_PIN = 16
SCL_PIN = 17
I2C_NUMMER = 0
I2C_ADDR = 0x27
I2C_ROWS = 2
I2C_COLS = 16

i2c = I2C(I2C_NUMMER, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

# ----- Initialisation du capteur de courant ACS712 -----
BROCHE_ACS712 = 26  # Utiliser GP26 (ADC0)
adc = ADC(Pin(BROCHE_ACS712))

# ----- Variables pour les mesures de tension -----
last_voltage = 0
current_voltage = 40
current_amperes = 0
current_battery_voltage = 0
TENSION_OFFSET = 2.540
SENSIBILITE = 0.066
# ----- Globales -----
timer1 = Timer()
timer2 = Timer()
timer3 = Timer()
timer4 = Timer()
timer5 = Timer()  # Nouveau timer pour mesurer la tension
mode_clignotement = 0
etat_clignotement = False
clignotement_detresse = False
indice_neo = 0
etat_bouton_gauche = 0
etat_bouton_droit = 0
etat_bande_rouge = 0
etat_bande_detresse = 0
phare_arriere_allumer = False
phare_avant = 0
numPage = 0
delai_rebond = 200
nombre_impulsions_reed = 0
temps_dernier_appui_gauche = 0
temps_dernier_appui_droit = 0
temps_dernier_appui_rouge = 0
temps_dernier_appuie_detresse = 0
temps_dernier_appui_page = 0
temps_dernier_appui_arriere = 0
temps_dernier_appui_phare = 0
temps_dernier_appui_chrono = 0
last_pedal_activity = 0 
pedal_timeout = 3000 
clignotant_actif = False  # Nouvelle variable pour suivre si un clignotant est actif

# Variables pour le chronometre
etat_chrono = 0
chrono_start_time = 0
chrono_elapsed_time = 0

# Variables pour les données de puissance
current_power = 0
current_cadence = 0
current_heartrate = 0
current_battery = 0
ble_connected = False
ble_hr_connected = False

# Variables pour la gestion de reconnexion BLE
last_ble_check = time.ticks_ms()
ble_check_interval = 30000  # 30 secondes entre les tentatives de reconnexion
ble_scan_timeout = 5000     # 5 secondes de scan maximum par tentative
scan_start_time = 0         # Pour suivre le temps de scan actuel
is_scanning = False         # Indicateur de scan en cours


# Créer une instance de AssiomaBLEClient
assioma_client = assioma.AssiomaBLEClient()

# ----- Fonctions -----
def clignoter(timer):
    global indice_neo, etat_clignotement

    if etat_clignotement:
        np[indice_neo] = COULEUR_ALLUME
    else:
        np[indice_neo] = COULEUR_ETEINT

    np.write()
    if mode_clignotement == 0:
        passer_neo_gauche()
    else:
        passer_neo_droit()
    etat_clignotement = not etat_clignotement

def Phare_arrière():
    if phare_arriere_allumer:
        for i in range(26):
            np[26+i] = COULEUR_ROUGE
    else:
        for i in range(26):
            np[26+i] = COULEUR_ETEINT
    np.write()

def passer_neo_gauche():
    global indice_neo, etat_clignotement
    np[indice_neo] = COULEUR_ETEINT
    indice_neo += 1
    if indice_neo > INDICE_FIN_GAUCHE:
        indice_neo = INDICE_DEBUT_GAUCHE
    etat_clignotement = False

def passer_neo_droit():
    global indice_neo, etat_clignotement
    np[indice_neo] = COULEUR_ETEINT
    indice_neo -= 1
    if indice_neo < INDICE_FIN_DROIT:
        indice_neo = INDICE_DEBUT_DROIT
    etat_clignotement = False

def eteindre_led(debut, fin):
    for i in range(min(debut, fin), max(debut, fin) + 1):
        np[i] = COULEUR_ETEINT
    np.write()

# Fonction pour lire l'ADC avec plusieurs échantillons pour réduire le bruit
def lire_adc(num_samples=5):
    total = 0
    for _ in range(num_samples):
        total += adc.read_u16()
    
    avg_value = total / num_samples
    tension = (avg_value / 65535) * 3.3
    
    # Calculer le courant à partir de la tension
    courant = (tension - TENSION_OFFSET) / SENSIBILITE
    courant = abs(courant)
    
    return tension, courant

# Fonction pour mettre à jour périodiquement la mesure de tension
def mise_a_jour_tension(timer):
    global current_voltage, current_amperes, current_battery_voltage
    current_voltage, current_amperes = lire_adc()
    # Calculer la tension de la batterie (Courant * 40V)
    current_battery_voltage = current_amperes * 40

def calculer_tension_batterie():
    """
    Calcule la tension de la batterie basée sur le courant mesuré
    Tension batterie = Courant * 40V
    """
    global current_amperes, current_battery_voltage
    current_battery_voltage = current_amperes * 40
    return current_battery_voltage

def ecran_page(numPage):
    global current_power, current_battery, ble_connected, is_scanning, current_voltage, current_battery_voltage
    
    # Mise à jour des données depuis le module assioma
    if assioma_client.conn_handle is not None:
        current_power = assioma_client.get_current_power()
        current_battery = assioma_client.get_battery_level()
        ble_connected = True
    else:
        ble_connected = False
    
    # On efface le contenu précédent dans la zone d'affichage des données
    oled.fill_rect(0, 20, 128, 44, 0)
    
    if numPage == 0:
        oled.text("Puissance mec:", 1, 20, 1)
        oled.text(f"{current_power} Watts", 1, 30, 1)

    elif numPage == 1:
        oled.text("Puissance elec:", 1, 20, 1)
        oled.text(f"Courant: {current_amperes:.3f}A", 1, 30, 1)
        # Ajouter l'affichage de la tension de la batterie
        oled.text(f"Puissance: {current_battery_voltage:.1f}W", 1, 40, 1)
        
    elif numPage == 2:
        # Affiche l'état de connexion BLE
        oled.text("BLE Status:", 1, 20, 1)
        if ble_connected:
            oled.text("Assioma: OK", 1, 30, 1)
        else:
            if is_scanning:
                oled.text("Recherche...", 1, 30, 1)
            else:
                oled.text("Assioma: Deconnecte", 1, 30, 1)
                oled.text("Attente 30s...", 1, 40, 1)
        
    elif numPage == 3:
        speed = vitesse.current_speed if hasattr(vitesse, 'current_speed') else 0
        # Nouvelle page pour afficher la vitesse
        oled.text("Vitesse:", 1, 20, 1)
        oled.text(f"{speed:.2f} km/h", 1, 30, 1)

    elif numPage == 4:
        oled.text("Batterie pedale:", 1, 20, 1)
        if ble_connected:
            oled.text(f"{current_battery}%", 1, 30, 1)
        else:
            oled.text("Non disponible", 1, 30, 1)
    elif numPage == 5:
        oled.text("Chrono:", 1, 20, 1)
        minutes = int(chrono_elapsed_time // 60)
        secondes = int(chrono_elapsed_time % 60)
        oled.text(f"{minutes:02d}:{secondes:02d}", 1, 30, 1)
    
    # Important: Appeler show() après avoir modifié l'affichage
    oled.show()
    

def ecran_clignotant():
    # Efface la partie supérieure pour les indicateurs
    oled.fill_rect(0, 0, 128, 16, 0)
    
    if etat_bande_detresse == 1:
        oled.fill_rect(1, 1, 10, 10, 1)
        oled.fill_rect(107, 2, 10, 10, 1)
        oled.text("D", 108, 1, 0)
        oled.text("G", 2, 1, 0)
        oled.show()
    else:
        if etat_bouton_gauche == 1:
            oled.fill_rect(1, 1, 10, 10, 1)
            oled.text("G", 2, 2, 0)
        else:
            oled.fill_rect(1, 1, 10, 10, 0)
            
        if etat_bouton_droit == 1:
            oled.fill_rect(107, 1, 10, 10, 1)
            oled.text("D", 108, 2, 0)
        else:
            oled.fill_rect(107, 1, 11, 11, 0)
    
    if phare_avant == 0:
        oled.fill_rect(30, 1, 20, 20, 0)
    else:
        oled.fill_rect(30, 1, 16, 10, 1)
        oled.text("PF", 31, 2, 0)
        
    if phare_arriere_allumer == 1:
        oled.fill_rect(70, 1, 16, 10, 1)
        oled.text("PR", 71, 2, 0)
    else:
        oled.fill_rect(70, 1, 20, 20, 0)
        oled.text("PR", 71, 2, 0)
        
    oled.show()

def pedale_info(timer):
    global current_battery, current_power, last_pedal_activity
    
    current_time = time.ticks_ms()
    
    if assioma_client.conn_handle is not None:
        assioma_client.read_battery_level()
        current_battery = assioma_client.get_battery_level()
        
        # Lire la puissance actuelle
        new_power = assioma_client.get_current_power()
        
        # Si la puissance est supérieure à 0, mettre à jour le timestamp d'activité
        if new_power > 0:
            current_power = new_power
            last_pedal_activity = current_time
        else:
            # Vérifier si il n'y a pas eu d'activité depuis 3 secondes
            if time.ticks_diff(current_time, last_pedal_activity) > pedal_timeout:
                current_power = 0
            # Sinon, garder la dernière valeur de puissance
        
    else:
        # Si pas de connexion, remettre la puissance à 0
        current_power = 0
    
    wdt.feed()

def gerer_feux_detresse(timer):
    global clignotement_detresse
    if clignotement_detresse:
        for i in range(0, 7):
            np[i] = COULEUR_ALLUME
        for i in range(19, 26):
            np[i] = COULEUR_ALLUME
    else:
        for i in range(0, 7):
            np[i] = COULEUR_ETEINT
        for i in range(19, 26):
            np[i] = COULEUR_ETEINT
    if etat_bande_detresse == False:
        for i in range(0, 7):
            np[i] = COULEUR_ETEINT
        for i in range(19, 26):
            np[i] = COULEUR_ETEINT
    np.write()
    clignotement_detresse = not clignotement_detresse

def gerer_bande_rouge(timer):
    if etat_bande_rouge == 1:
        for i in range(7, 19):
            np[i] = COULEUR_ROUGE
    else:
        for i in range(7, 19):
            np[i] = COULEUR_ETEINT
    np.write()

def allumer_phare():
    if phare_avant == 1:
        pwm.duty_u16(16000)
    elif phare_avant == 2:
        pwm.duty_u16(32000)
    elif phare_avant == 3:
        pwm.duty_u16(65535)
    else:
        pwm.duty_u16(0)

# Nouvelle fonction pour gérer les tentatives de connexion BLE
def gerer_connexion_ble():
    global last_ble_check, is_scanning, scan_start_time, ble_connected
    
    current_time = time.ticks_ms()
    
    # Vérifier si nous sommes connectés
    if assioma_client.conn_handle is not None:
        ble_connected = True
        is_scanning = False
        return True
    else:
        ble_connected = False
    
    # Si un scan est en cours, vérifier s'il a expiré
    if is_scanning:
        if time.ticks_diff(current_time, scan_start_time) > ble_scan_timeout:
            # Le scan a duré trop longtemps, on l'arrête
            assioma_client.stop_scan()
            is_scanning = False
            last_ble_check = current_time  # Réinitialiser le timer de contrôle
    
    # Si aucun scan n'est en cours et qu'il est temps de vérifier à nouveau
    elif time.ticks_diff(current_time, last_ble_check) > ble_check_interval:
        print("Démarrage d'un nouveau scan BLE")
        assioma_client.stop_scan()  # S'assurer qu'aucun scan précédent n'est actif
        time.sleep_ms(100)          # Court délai pour stabilisation
        assioma_client.start_scan()
        is_scanning = True
        scan_start_time = current_time
    
    return False

def mettre_a_jour_chronometre(timer):
    global chrono_elapsed_time, chrono_start_time
    chrono_elapsed_time = time.time() - chrono_start_time

def gerer_boutons(bouton):
    global etat_bouton_gauche, etat_bouton_droit, mode_clignotement
    global indice_neo, etat_clignotement, timer1, etat_bande_rouge
    global etat_bande_detresse, temps_dernier_appui_gauche, temps_dernier_appui_droit
    global temps_dernier_appui_rouge, temps_dernier_appuie_detresse, temps_dernier_appui_page
    global numPage, timer2, temps_dernier_appui_arriere, phare_arriere_allumer, phare_avant
    global temps_dernier_appui_phare, clignotant_actif, temps_dernier_appui_chrono
    global chrono_elapsed_time, chrono_start_time, etat_chrono
    temps_actuel = time.ticks_ms()
    # Clignotant Gauche
    if bouton == bouton_gauche and etat_bande_detresse == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_gauche) > delai_rebond:
            temps_dernier_appui_gauche = temps_actuel
            if etat_bouton_gauche == 0:
                etat_bouton_gauche = 1
                etat_bouton_droit = 0  # Éteindre l'autre clignotant
                mode_clignotement = 0
                indice_neo = INDICE_DEBUT_GAUCHE
                etat_clignotement = True
                timer1.init(freq=4, mode=Timer.PERIODIC, callback=clignoter)
                clignotant_actif = True
                
            else:
                etat_bouton_gauche = 0
                etat_clignotement = False
                timer1.deinit()
                eteindre_led(INDICE_DEBUT_GAUCHE, INDICE_FIN_GAUCHE)
                clignotant_actif = False
            ecran_clignotant()
            
    # Clignotant Droit
    elif bouton == bouton_droit and etat_bande_detresse == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_droit) > delai_rebond:
            temps_dernier_appui_droit = temps_actuel
            if etat_bouton_droit == 0:
                etat_bouton_droit = 1
                etat_bouton_gauche = 0  # Éteindre l'autre clignotant
                mode_clignotement = 1
                indice_neo = INDICE_DEBUT_DROIT
                etat_clignotement = True
                timer1.init(freq=4, mode=Timer.PERIODIC, callback=clignoter)
                clignotant_actif = True
               
            else:
                etat_bouton_droit = 0
                etat_clignotement = False
                timer1.deinit()
                eteindre_led(INDICE_FIN_DROIT, INDICE_DEBUT_DROIT)
                clignotant_actif = False
            ecran_clignotant()

    elif bouton == bouton_page:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_page) > delai_rebond:
            # Lecture des informations de pédale à chaque changement de page
            if assioma_client.conn_handle is not None:
                assioma_client.read_battery_level()
                current_battery = assioma_client.get_battery_level()
                
            temps_dernier_appui_page = temps_actuel
            numPage += 1
            oled.fill(0)
            ecran_clignotant()
            if numPage == 6:
                numPage = 0
            ecran_page(numPage)

    # Bande rouge
    elif bouton == frein:
        timer2.init(freq=6, mode=Timer.PERIODIC, callback=gerer_bande_rouge)
        temps_dernier_appui_rouge = temps_actuel
        etat_bande_rouge ^= 1
        
    # Feux de détresse
    elif bouton == bouton_feux_detresse:
        if time.ticks_diff(temps_actuel, temps_dernier_appuie_detresse) > delai_rebond:
            temps_dernier_appuie_detresse = temps_actuel
            etat_bande_detresse = 1 - etat_bande_detresse
            if etat_bande_detresse == 1:
                timer1.init(freq=5, mode=Timer.PERIODIC, callback=gerer_feux_detresse)
                etat_bouton_droit = 0
                etat_bouton_gauche = 0
                if clignotant_actif:
                    timer1.deinit()
                    eteindre_led(INDICE_DEBUT_GAUCHE, INDICE_FIN_GAUCHE)
                    eteindre_led(INDICE_FIN_DROIT, INDICE_DEBUT_DROIT)
                    clignotant_actif = False
            else:
                etat_clignotement = False
                gerer_feux_detresse(timer1)
                timer1.deinit()
            ecran_clignotant()
            
    elif bouton == bouton_arriere:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_arriere) > delai_rebond:
            temps_dernier_appui_arriere = temps_actuel
            phare_arriere_allumer = 1 - phare_arriere_allumer
            Phare_arrière()
            ecran_clignotant()

    elif bouton == bouton_phare:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_phare) > delai_rebond:
            temps_dernier_appui_phare = temps_actuel
            if phare_avant < 3:
                phare_avant += 1
            else:
                phare_avant = 0
            allumer_phare()
            ecran_clignotant()

    elif bouton == bouton_chrono:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_chrono) > delai_rebond:
            temps_dernier_appui_chrono = temps_actuel
            etat_chrono = 1 - etat_chrono
            if etat_chrono:
                chrono_start_time = time.time()
                chrono_elapsed_time = 0
                timer4.init(freq=1, mode=Timer.PERIODIC, callback=mettre_a_jour_chronometre)
            else:
                timer4.deinit()

# Configure les interruptions des boutons
bouton_droit.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_gauche.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
frein.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING)
bouton_feux_detresse.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_page.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_arriere.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_reed.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_phare.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)
bouton_chrono.irq(handler=lambda pin: gerer_boutons(pin), trigger=Pin.IRQ_FALLING)


# Initialisation de l'écran
oled.fill(0)
ecran_clignotant()
ecran_page(numPage)

wdt = WDT(timeout=8000)
# Démarrer le scan BLE dès le départ
assioma_client.start_scan()
is_scanning = True
scan_start_time = time.ticks_ms()

# Configuration du timer pour la mise à jour périodique des données de la pédale
timer3.init(freq=10, mode=Timer.PERIODIC, callback=pedale_info)  # Mise à jour toutes les 5 secondes

# Configuration du timer pour la mise à jour périodique de la tension
timer5.init(freq=0.5, mode=Timer.PERIODIC, callback=mise_a_jour_tension)  # Mise à jour toutes les 0.5 secondes

# ----- Boucle principale -----a
while True:
    # Gestion de la connexion BLE
    gerer_connexion_ble()
    
    # Mise à jour de l'écran
    ecran_page(numPage)
    
    wdt.feed()
    time.sleep_ms(100)  # Un petit délai pour éviter de surcharger le processeur