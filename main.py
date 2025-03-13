import machine
import neopixel
import time

# Configuration des NeoPixels
BROCHE_NEO = 2
NOMBRE_NEO = 26
np = neopixel.NeoPixel(machine.Pin(BROCHE_NEO), NOMBRE_NEO)

# Valeurs de couleur pour les NeoPixels
COULEUR_ALLUME = (255, 60, 0)
COULEUR_ETEINT = (0, 0, 0)
COULEUR_ROUGE = (120, 0, 0)

# Indices de début et de fin pour chaque mode
INDICE_DEBUT_GAUCHE = 19
INDICE_FIN_GAUCHE = 25
INDICE_DEBUT_DROIT = 5
INDICE_FIN_DROIT = 0

# Configuration des boutons
BROCHE_BOUTON_GAUCHE = 15
BROCHE_BOUTON_DROIT = 16
BROCHE_BOUTON_ROUGE = 14
BROCHE_FEUX_DETRESSE = 17
bouton_feux_detresse = machine.Pin(BROCHE_FEUX_DETRESSE, machine.Pin.IN, machine.Pin.PULL_UP)
bouton_gauche = machine.Pin(BROCHE_BOUTON_GAUCHE, machine.Pin.IN, machine.Pin.PULL_UP)
bouton_droit = machine.Pin(BROCHE_BOUTON_DROIT, machine.Pin.IN, machine.Pin.PULL_UP)
bouton_rouge = machine.Pin(BROCHE_BOUTON_ROUGE, machine.Pin.IN, machine.Pin.PULL_UP)

# Configuration du timer
timer1 = machine.Timer()

# Variables globales
mode_clignotement = 0
etat_clignotement = False
clignotement_detresse = False
indice_neo = 0
etat_bouton_gauche = 0
etat_bouton_droit = 0
etat_bande_rouge = 0  # État de la bande rouge (0: éteinte, 1: allumée)
etat_bande_detresse = 0
temps_dernier_appui_gauche = 0
temps_dernier_appui_droit = 0
temps_dernier_appui_rouge = 0
temps_dernier_appuie_detresse = 0
delai_rebond = 200

# Fonction de rappel du timer pour le clignotement
def clignoter(timer):
    global indice_neo, etat_clignotement, etat_bande_rouge
    if etat_clignotement:
        np[indice_neo] = COULEUR_ETEINT
    else:
        np[indice_neo] = COULEUR_ALLUME
    if etat_bande_rouge == 1:
        for i in range(7, 19):
            np[i] = COULEUR_ROUGE
    np.write()
    etat_clignotement = not etat_clignotement

# Fonction pour passer au NeoPixel suivant (gauche)
def passer_neo_gauche():
    global indice_neo, etat_clignotement
    np[indice_neo] = COULEUR_ETEINT
    indice_neo += 1
    if indice_neo > INDICE_FIN_GAUCHE:
        indice_neo = INDICE_DEBUT_GAUCHE
    etat_clignotement = False

# Fonction pour passer au NeoPixel suivant (droit)
def passer_neo_droit():
    global indice_neo, etat_clignotement
    np[indice_neo] = COULEUR_ETEINT
    indice_neo -= 1
    if indice_neo < INDICE_FIN_DROIT:
        indice_neo = INDICE_DEBUT_DROIT
    etat_clignotement = False

# Fonction pour gérer les boutons
def gerer_boutons():
    global etat_bouton_gauche, etat_bouton_droit, mode_clignotement, indice_neo, etat_clignotement, timer1, etat_bande_rouge, etat_bande_detresse, temps_dernier_appui_gauche, temps_dernier_appui_droit, temps_dernier_appui_rouge, temps_dernier_appuie_detresse, delai_rebond
    temps_actuel = time.ticks_ms()

    if etat_bande_detresse == 0:
        if bouton_gauche.value() == 0:
            if time.ticks_diff(temps_actuel, temps_dernier_appui_gauche) > delai_rebond:
                temps_dernier_appui_gauche = temps_actuel
                etat_bouton_gauche = 1 - etat_bouton_gauche
                if etat_bouton_gauche == 1:
                    mode_clignotement = 0
                    indice_neo = INDICE_DEBUT_GAUCHE
                    etat_clignotement = True
                    timer1.init(freq=5, mode=machine.Timer.PERIODIC, callback=clignoter)
                else:
                    etat_clignotement = False
                    timer1.deinit()
                    for i in range(NOMBRE_NEO):
                        np[i] = COULEUR_ETEINT
                    np.write()

        if bouton_droit.value() == 0:
            if time.ticks_diff(temps_actuel, temps_dernier_appui_droit) > delai_rebond:
                temps_dernier_appui_droit = temps_actuel
                etat_bouton_droit = 1 - etat_bouton_droit
                if etat_bouton_droit == 1:
                    mode_clignotement = 1
                    indice_neo = INDICE_FIN_DROIT
                    etat_clignotement = True
                    timer1.init(freq=5, mode=machine.Timer.PERIODIC, callback=clignoter)
                else:
                    etat_clignotement = False
                    timer1.deinit()
                    for i in range(NOMBRE_NEO):
                        np[i] = COULEUR_ETEINT
                    np.write()

    if bouton_rouge.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appui_rouge) > delai_rebond:
            temps_dernier_appui_rouge = temps_actuel
            etat_bande_rouge = 1 - etat_bande_rouge
    if bouton_feux_detresse.value() == 0:
        if time.ticks_diff(temps_actuel, temps_dernier_appuie_detresse) > delai_rebond:
            temps_dernier_appuie_detresse = temps_actuel
            etat_bande_detresse = 1 - etat_bande_detresse
            if etat_bande_detresse == 1:
                timer1.init(freq=5, mode=machine.Timer.PERIODIC, callback=gerer_feux_detresse)
                if etat_bouton_droit == 1:
                    etat_bouton_droit = 1 - etat_bouton_droit
                if etat_bouton_gauche ==1 :
                    etat_bouton_gauche = 1 -etat_bouton_gauche
            else :
                etat_clignotement = False
                for i in range(0,7):
                    np[i] = COULEUR_ETEINT
                for i in range(19,26):
                    np[i] = COULEUR_ETEINT
                np.write()
                timer1.deinit()

        
def gerer_feux_detresse(timer) :
    global clignotement_detresse
    if clignotement_detresse:
        for i in range (0,7):
            np[i] = COULEUR_ALLUME
        for i in range (19,26):
            np[i] = COULEUR_ALLUME
    else :
        for i in range (0,7):
            np[i] = COULEUR_ETEINT
        for i in range (19,26):
            np[i] = COULEUR_ETEINT
    np.write()
    clignotement_detresse = not clignotement_detresse
# Fonction pour allumer ou éteindre la bande rouge
def gerer_bande_rouge():
    global etat_bande_rouge
    if etat_bande_rouge == 1:
        for i in range(7, 19):
            np[i] = COULEUR_ROUGE
    else:
        for i in range(7, 19):
            np[i] = COULEUR_ETEINT
    np.write()

# Boucle principale
temps_debut = 0
while True:
    gerer_boutons()
    if etat_clignotement:
        if mode_clignotement == 0:
            passer_neo_gauche()
        else:
            passer_neo_droit()
    gerer_bande_rouge()  # Appeler la fonction pour gérer la bande rouge
    time.sleep_ms(10)