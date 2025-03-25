from machine import Pin, Timer, I2C
import neopixel
import time
from api_I2C import LcdApi
from pico_i2c_lcd import I2cLcd

# ----- NeoPixel Configuration -----
BROCHE_NEO = 2
NOMBRE_NEO = 26
np = neopixel.NeoPixel(Pin(2), NOMBRE_NEO)
BROCHE_PHARE = 19
NOMBRE_NEO_PHARE = 24
np_phare = neopixel.NeoPixel(Pin(19), NOMBRE_NEO)

COULEUR_ALLUME = (255, 60, 0)
COULEUR_ETEINT = (0, 0, 0)
COULEUR_ROUGE = (120, 0, 0)

INDICE_DEBUT_GAUCHE = 19
INDICE_FIN_GAUCHE = 25
INDICE_DEBUT_DROIT = 6
INDICE_FIN_DROIT = 0

# ----- Boutons -----
BROCHE_BOUTON_GAUCHE = 15
BROCHE_BOUTON_DROIT = 16
BROCHE_BOUTON_ROUGE = 14
BROCHE_FEUX_DETRESSE = 17
BROCHE_PAGE = 18
BROCHE_ARRIERE = 20
bouton_gauche = Pin(BROCHE_BOUTON_GAUCHE, Pin.IN, Pin.PULL_UP)
bouton_droit = Pin(BROCHE_BOUTON_DROIT, Pin.IN, Pin.PULL_UP)
bouton_rouge = Pin(BROCHE_BOUTON_ROUGE, Pin.IN, Pin.PULL_UP)
bouton_feux_detresse = Pin(BROCHE_FEUX_DETRESSE, Pin.IN, Pin.PULL_UP)
bouton_page = Pin(BROCHE_PAGE, Pin.IN, Pin.PULL_UP)
bouton_arriere = Pin(BROCHE_ARRIERE, Pin.IN, Pin.PULL_UP)


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
timer2 = Timer()
timer3 = Timer()
mode_clignotement = 0
etat_clignotement = False
clignotement_detresse = False
indice_neo = 0
etat_bouton_gauche = 0
etat_bouton_droit = 0
etat_bande_rouge = 0
etat_bande_detresse = 0
phare_allumer = False
numPage = 0
delai_rebond = 200

temps_dernier_appui_gauche = 0
temps_dernier_appui_droit = 0
temps_dernier_appui_rouge = 0
temps_dernier_appuie_detresse = 0
temps_dernier_appui_page = 0
temps_dernier_appui_arriere = 0

# ----- Fonctions -----
def clignoter(timer):
    global indice_neo, etat_clignotement
    if etat_clignotement:
        np[indice_neo] = COULEUR_ALLUME
    else:
        np[indice_neo] = COULEUR_ETEINT

    np.write()
    if mode_clignotement == 0 :
        passer_neo_gauche()
    else :
        passer_neo_droit()
    etat_clignotement = not etat_clignotement

def Phare_arrière():
    if phare_allumer:
        for i in range(NOMBRE_NEO_PHARE):
            np_phare[i] = COULEUR_ROUGE
    else :
        for i in range(NOMBRE_NEO_PHARE):
            np_phare[i] = COULEUR_ETEINT
    np_phare.write()

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

def ecran_page(numPage) :
    if numPage == 0:
        lcd.move_to(2,0)
        lcd.putstr("Kilometrage")
    if numPage == 1 :
        lcd.move_to(2,0)
        lcd.putstr("consom elec")
    if numPage == 2 :
        lcd.move_to(2,0)
        lcd.putstr("freq card   ")

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

def gerer_boutons(bouton):
    global etat_bouton_gauche, etat_bouton_droit, mode_clignotement
    global indice_neo, etat_clignotement, timer1, etat_bande_rouge
    global etat_bande_detresse, temps_dernier_appui_gauche, temps_dernier_appui_droit
    global temps_dernier_appui_rouge, temps_dernier_appuie_detresse, temps_dernier_appui_page
    global numPage, timer2, temps_dernier_appui_arriere, phare_allumer

    temps_actuel = time.ticks_ms()

    # Clignotant Gauche
    if etat_bande_detresse == 0 and bouton_gauche.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_gauche) > delai_rebond:
            temps_dernier_appui_gauche = temps_actuel
            etat_bouton_gauche = 1 - etat_bouton_gauche
            if etat_bouton_gauche == 1:
                if etat_bouton_droit == 1 :
                    etat_bouton_droit = 1 - etat_bouton_droit
                mode_clignotement = 0
                indice_neo = INDICE_DEBUT_GAUCHE
                etat_clignotement = True
                timer1.init(freq=4, mode=Timer.PERIODIC, callback=clignoter)
                try:
                    lcd.move_to(15,0)
                    lcd.putstr(" ")
                    lcd.move_to(0, 0)
                    lcd.putstr("G")  # ← Affiche G pour gauche
                except OSError as e:
                    print("Erreur LCD lors de l'affichage G:", e)
            else:
                etat_clignotement = False
                timer1.deinit()

                try:

                    lcd.move_to(0, 0)
                    lcd.putstr(" ")  # Efface G
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G:", e)

    # Clignotant Droit
    if etat_bande_detresse == 0 and bouton_droit.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_droit) > delai_rebond:
            temps_dernier_appui_droit = temps_actuel
            etat_bouton_droit = 1 - etat_bouton_droit
            if etat_bouton_droit == 1:
                if etat_bouton_gauche == 1 :
                    etat_bouton_gauche = 1 - etat_bouton_gauche
                mode_clignotement = 1
                indice_neo = INDICE_DEBUT_DROIT
                etat_clignotement = True
                timer1.init(freq=4, mode=Timer.PERIODIC, callback=clignoter)
                try:
                    lcd.move_to(0,0)
                    lcd.putstr(" ")
                    lcd.move_to(15, 0)
                    lcd.putstr("D")  # ← Affiche D pour droit
                except OSError as e:
                    print("Erreur LCD lors de l'affichage D:", e)
            else:
                etat_clignotement = False
                timer1.deinit()
                try:
                    lcd.move_to(15, 0)
                    lcd.putstr(" ")  # Efface D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de D:", e)
    if bouton_page.value() ==0 :
        if time.ticks_diff(temps_actuel, temps_dernier_appui_page) > delai_rebond :
            timer3.init(freq=1,mode=Timer.PERIODIC, callback=ecran_page)
            ecran_page(numPage)
            temps_dernier_appui_page = temps_actuel
            numPage += 1
            if numPage == 3 :
                numPage = 0
            
    # Bande rouge
    if bouton_rouge.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_rouge) > delai_rebond:
            timer2.init(freq=6, mode=Timer.PERIODIC, callback=gerer_bande_rouge)
            temps_dernier_appui_rouge = temps_actuel
            etat_bande_rouge ^= 1

    # Feux de détresse
    if bouton_feux_detresse.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appuie_detresse) > delai_rebond:
            temps_dernier_appuie_detresse = temps_actuel
            etat_bande_detresse = 1 - etat_bande_detresse
            if etat_bande_detresse == 1:
                timer1.init(freq=5, mode=Timer.PERIODIC, callback=gerer_feux_detresse)
                etat_bouton_droit = 0
                etat_bouton_gauche = 0
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr("G")  # affiche G et D
                    lcd.move_to(15, 0)
                    lcd.putstr("D")  # affiche G et D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G et D:", e)
            else:
                etat_clignotement = False
                gerer_feux_detresse(timer1)
                timer1.deinit()
                try:
                    lcd.move_to(0, 0)
                    lcd.putstr(" ")  # Efface G et D
                    lcd.move_to(15, 0)
                    lcd.putstr(" ")  # Efface G et D
                except OSError as e:
                    print("Erreur LCD lors de l'effacement de G et D:", e)

    if bouton_arriere.value() ==0:
        if time.ticks_diff(temps_actuel,temps_dernier_appui_arriere):
            temps_dernier_appui_arriere = temps_actuel
            phare_allumer = 1 - phare_allumer
            Phare_arrière()
bouton_droit.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)
bouton_gauche.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)
bouton_rouge.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)
bouton_feux_detresse.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)
bouton_page.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)
bouton_arriere.irq(handler=gerer_boutons,trigger=Pin.IRQ_FALLING)

# ----- Boucle principale -----
while True:
    #gerer_boutons()
    a=0
