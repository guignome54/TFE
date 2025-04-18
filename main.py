from machine import Pin, Timer, I2C, PWM
import neopixel
import time
from ssd1306 import SSD1306_I2C


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
BROCHE_REED = 21
BROCHE_PHARE = 9
BROCHE_AFFICHAGE_PHARE = 8
bouton_gauche = Pin(BROCHE_BOUTON_GAUCHE, Pin.IN, Pin.PULL_UP)
bouton_droit = Pin(BROCHE_BOUTON_DROIT, Pin.IN, Pin.PULL_UP)
bouton_rouge = Pin(BROCHE_BOUTON_ROUGE, Pin.IN, Pin.PULL_UP)
bouton_feux_detresse = Pin(BROCHE_FEUX_DETRESSE, Pin.IN, Pin.PULL_UP)
bouton_page = Pin(BROCHE_PAGE, Pin.IN, Pin.PULL_UP)
bouton_arriere = Pin(BROCHE_ARRIERE, Pin.IN, Pin.PULL_UP)
bouton_reed = Pin(BROCHE_REED, Pin.IN, Pin.PULL_UP)
bouton_phare = Pin(BROCHE_PHARE,Pin.IN,Pin.PULL_UP)

pwm = PWM(8,144)
# ----- LCD (I2C) -----
SDA_PIN = 6
SCL_PIN = 7
I2C_NUMMER = 1
I2C_ADDR = 0x27
I2C_ROWS = 2
I2C_COLS = 16

i2c = I2C(I2C_NUMMER, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)


# ----- Globales -----
timer1 = Timer()
timer2 = Timer()
timer3 = Timer()
timer4 = Timer()
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
clignotant_actif = False # Nouvelle variable pour suivre si un clignotant est actif

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
    if phare_arriere_allumer:
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

def eteindre_led(debut, fin):
    for i in range(debut,fin + 1): # Correction ici pour inclure la fin
        np[i] = COULEUR_ETEINT
    np.write()
def ecran_page(numPage) :
    # On redessine la zone où le texte était affiché avec la couleur de fond (ici, noir)

    if numPage == 0:
        oled.text("puissance elec-", 1, 20, 1)
        oled.text("trique", 1, 30, 1)
        oled.show()

    elif numPage == 1 :
        oled.text("puissance mec-", 1, 20, 1)
        oled.text("anique", 1, 30, 1)
        oled.show()
    elif numPage == 2 :
        pass
def ecran_clignotant():
    if etat_bande_detresse == 1 :
        oled.fill_rect(1, 1, 10, 10, 1)
        oled.fill_rect(107, 2, 10, 10, 1)
        oled.text("D",108,1,0)
        oled.text("G",2,1,0)
        oled.show()
    else :
        if etat_bouton_gauche == 1 :
            oled.fill_rect(1, 1, 10, 10, 1)
            oled.text("G",2,2,0)
            oled.show()
        else :
            oled.fill_rect(1, 1, 10, 10, 0)
            oled.show()
        if etat_bouton_droit == 1:
            oled.fill_rect(107, 1, 10, 10, 1)
            oled.text("D",108,2,0)
            oled.show()
        else :
            oled.fill_rect(107, 1, 11, 11, 0)
            oled.show()
    if phare_avant == 0 :
        oled.fill_rect(30, 1, 20, 20, 0)
        oled.show()
    else :
        oled.fill_rect(30, 1, 16, 10, 1)
        oled.text("PF",31,2,0)
        oled.show()
    if phare_arriere_allumer == 1 :
        oled.fill_rect(70, 1, 16, 10, 1)
        oled.text("PR",71,2,0)
        oled.show()
    else :
        oled.fill_rect(70, 1, 20, 20, 0)
        oled.text("PR",71,2,0)
        oled.show()
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
    if phare_avant == 1 :
        pwm.duty_u16(16000)
    elif phare_avant == 2 :
        pwm.duty_u16(32000)
    elif phare_avant == 3:
        pwm.duty_u16(65535)
    else:
        pwm.duty_u16(0)

def gerer_boutons(bouton):
    global etat_bouton_gauche, etat_bouton_droit, mode_clignotement
    global indice_neo, etat_clignotement, timer1, etat_bande_rouge
    global etat_bande_detresse, temps_dernier_appui_gauche, temps_dernier_appui_droit
    global temps_dernier_appui_rouge, temps_dernier_appuie_detresse, temps_dernier_appui_page
    global numPage, timer2, temps_dernier_appui_arriere, phare_arriere_allumer, phare_avant
    global temps_dernier_appui_phare, clignotant_actif
    temps_actuel = time.ticks_ms()

    # Clignotant Gauche
    if bouton == bouton_gauche and etat_bande_detresse == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_gauche) > delai_rebond:
            temps_dernier_appui_gauche = temps_actuel
            if etat_bouton_gauche == 0:
                etat_bouton_gauche = 1
                etat_bouton_droit = 0 # Éteindre l'autre clignotant
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
                etat_bouton_gauche = 0 # Éteindre l'autre clignotant
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
        if time.ticks_diff(temps_actuel, temps_dernier_appui_page) > delai_rebond :
            temps_dernier_appui_page = temps_actuel
            numPage += 1
            oled.fill(0)
            ecran_clignotant()
            if numPage == 3 :
                numPage = 0

    # Bande rouge
    elif bouton == bouton_rouge:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_rouge) > delai_rebond:
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
        if time.ticks_diff(temps_actuel,temps_dernier_appui_arriere) > delai_rebond:
            temps_dernier_appui_arriere = temps_actuel
            phare_arriere_allumer = 1 - phare_arriere_allumer
            Phare_arrière()
            ecran_clignotant()

    elif bouton == bouton_phare:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_phare) > delai_rebond :
            temps_dernier_appui_phare = temps_actuel
            if phare_avant < 3 :
                phare_avant += 1
            else :
                phare_avant = 0
            allumer_phare()
            ecran_clignotant()

bouton_droit.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_gauche.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_rouge.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_feux_detresse.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_page.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_arriere.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_reed.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)
bouton_phare.irq(handler=lambda pin: gerer_boutons(pin),trigger=Pin.IRQ_FALLING)

ecran_page(numPage)
# ----- Boucle principale -----
while True:
    ecran_page(numPage)
    pass