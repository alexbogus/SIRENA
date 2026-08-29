# Instalación del entorno de desarrollo

```bash
brew tap espressif/eim
brew trust espressif/eim
brew install eim
```

## Configuración de la extensión ESP-IDF

```bash
"/opt/homebrew/bin/eim" wizard --idf-features ide
```

# Conectar la placa

Una vez configurada la extensión en VS-CODE, vamos a conectar la placa y comprobar que la vemos

```bash
ls /dev/cu.*
```
Veremos algo parecido a:

```
/dev/cu.usbmodem3122301
/dev/cu.usbmodem3122401
```

# Creación de un nuevo proyecto

Abrimos un terminal y configuramos el entorno

```bash
source /Users/alexcasanova/.espressif/tools/activate_idf_v6.1.sh
````


## Identificación del puerto usado por el speaker

```bash
ls /dev/cu.* > /tmp/ports-before.txt
ls /dev/cu.* > /tmp/ports-after.txt 
diff /tmp/ports-after.txt /tmp/ports-before.txt
```
Esto nos da como resultado `/dev/cu.usbmodem3122401`que será el puerto que vamos a utilizar. A partir de aquí, vamos a hacer pruebas para ver que todo es correcto antes de flashear nada.

```bash
idf.py -p /dev/cu.usbmodem3122401 flash
```