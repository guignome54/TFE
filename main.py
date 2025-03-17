from machine import Pin, Timer, I2C
import neopixel
import time
from api_I2C import LcdApi
from pico_i2c_lcd import I2cLcd

# ----- NeoPixel Configuration -----
BROCHE_NEO = 2
NOMBRE_NEO = 26
np = neopixel.NeoPixel(Pin(BROCHE_NEO), NOMBRE_NEO)

COULEUR_ALLUME = (255, 60, 0)
COULEUR_ETEINT = (0, 0, 0)
COULEUR_ROUGE = (120, 0, 0)

INDICE_DEBUT_GAUCHE = 19
INDICE_FIN_GAUCHE = 25
INDICE_DEBUT_DROIT = 5
INDICE_FIN_DROIT = 0

# ----- Boutons -----
BROCHE_BOUTON_GAUCHE = 15
BROCHE_BOUTON_DROIT = 16
BROCHE_BOUTON_ROUGE = 14
BROCHE_FEUX_DETRESSE = 17

bouton_gauche = Pin(BROCHE_BOUTON_GAUCHE, Pin.IN, Pin.PULL_UP)
bouton_droit = Pin(BROCHE_BOUTON_DROIT, Pin.IN, Pin.PULL_UP)
bouton_rouge = Pin(BROCHE_BOUTON_ROUGE, Pin.IN, Pin.PULL_UP)
bouton_feux_detresse = Pin(BROCHE_FEUX_DETRESSE, Pin.IN, Pin.PULL_UP)

# ----- LCD (I2C) -----
SDA_PIN = 6
SCL_PIN = 7
I2C_NUMMER = 1
I2C_ADDR = 0x27
I2C_ROWS = 2
I2C_COLS = 16

i2c = I2C(I2C_NUMMER, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

try:
    lcd = I2cLcd(i2c, I2C_ADDR, I2C_ROWS, I2C_COLS)
    lcd.backlight_on()
    lcd.clear()

except OSError as e:
    print("Erreur I2C lors de l'initialisation du LCD:", e)

# ----- Globales -----
timer1 = Timer()
mode_clignotement = 0
etat_clignotement = False
clignotement_detresse = False
indice_neo = 0
etat_bouton_gauche = 0
etat_bouton_droit = 0
etat_bande_rouge = 0
etat_bande_detresse = 0
delai_rebond = 200

temps_dernier_appui_gauche = 0
temps_dernier_appui_droit = 0
temps_dernier_appui_rouge = 0
temps_dernier_appuie_detresse = 0

# ----- Fonctions -----
def clignoter(timer):
    global indice_neo, etat_clignotement
    if etat_clignotement:
        np[indice_neo] = COULEUR_ETEINT
    else:
        np[indice_neo] = COULEUR_ALLUME
    if etat_bande_rouge == 1:
        for i in range(7, 19):
            np[i] = COULEUR_ROUGE
    np.write()
    etat_clignotement = not etat_clignotement

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
    np.write()
    clignotement_detresse = not clignotement_detresse

def gerer_bande_rouge():
    if etat_bande_rouge == 1:
        for i in range(7, 19):
            np[i] = COULEUR_ROUGE
    else:
        for i in range(7, 19):
            np[i] = COULEUR_ETEINT
    np.write()

def gerer_boutons():
    global etat_bouton_gauche, etat_bouton_droit, mode_clignotement
    global indice_neo, etat_clignotement, timer1, etat_bande_rouge
    global etat_bande_detresse, temps_dernier_appui_gauche, temps_dernier_appui_droit
    global temps_dernier_appui_rouge, temps_dernier_appuie_detresse

    temps_actuel = time.ticks_ms()

    # Clignotant Gauche
    if etat_bande_detresse == 0 and bouton_gauche.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_gauche) > delai_rebond:
            temps_dernier_appui_gauche = temps_actuel
            etat_bouton_gauche ^= 1
            if etat_bouton_gauche == 1:
                mode_clignotement = 0
                indice_neo = INDICE_DEBUT_GAUCHE
                etat_clignotement = True
                timer1.init(freq=5, mode=Timer.PERIODIC, callback=clignoter)
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr("G")  # ← Affiche G pour gauche
                except OSError as e:
                    print("Erreur LCD lors de l'affichage G:", e)
            else:
                etat_clignotement = False
                timer1.deinit()
                for i in range(NOMBRE_NEO):
                    np[i] = COULEUR_ETEINT
                np.write()
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr(" ")  # Efface G
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G:", e)

    # Clignotant Droit
    if etat_bande_detresse == 0 and bouton_droit.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_droit) > delai_rebond:
            temps_dernier_appui_droit = temps_actuel
            etat_bouton_droit ^= 1
            if etat_bouton_droit == 1:
                mode_clignotement = 1
                indice_neo = INDICE_FIN_DROIT
                etat_clignotement = True
                timer1.init(freq=5, mode=Timer.PERIODIC, callback=clignoter)
                try:
                    lcd.move_to(15, 0)
                    lcd.putstr("D")  # ← Affiche D pour droit
                except OSError as e:
                    print("Erreur LCD lors de l'affichage D:", e)
            else:
                etat_clignotement = False
                timer1.deinit()
                for i in range(NOMBRE_NEO):
                    np[i] = COULEUR_ETEINT
                np.write()
                try:
                    lcd.move_to(15, 0)
                    lcd.putstr(" ")  # Efface D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de D:", e)

    # Bande rouge
    if bouton_rouge.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_rouge) > delai_rebond:
            temps_dernier_appui_rouge = temps_actuel
            etat_bande_rouge ^= 1

    # Feux de détresse
    if bouton_feux_detresse.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appuie_detresse) > delai_rebond:
            temps_dernier_appuie_detresse = temps_actuel
            etat_bande_detresse ^= 1
            if etat_bande_detresse == 1:
                timer1.init(freq=5, mode=Timer.PERIODIC, callback=gerer_feux_detresse)
                etat_bouton_droit = 0
                etat_bouton_gauche = 0
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr("G")  # Efface G et D
                    lcd.move_to(15, 0)
                    lcd.putstr("D")  # Efface G et D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G et D:", e)
            else:
                etat_clignotement = False
                for i in list(range(0, 7)) + list(range(19, 26)):
                    np[i] = COULEUR_ETEINT
                np.write()
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr(" ")  # Efface G et D
                    lcd.move_to(15, 0)
                    lcd.putstr(" ")  # Efface G et D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G et D:", e)
                timer1.deinit()

# ----- Boucle principale -----
while True:
    gerer_boutons()
    if etat_clignotement:
        if mode_clignotement == 0:
            passer_neo_gauche()
        else:
            passer_neo_droit()
    gerer_bande_rouge()
