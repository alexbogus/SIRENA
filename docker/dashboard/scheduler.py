"""Instancia única del scheduler, en su propio módulo para que tanto app.py
como las rutas puedan importarla sin crear un import circular con app.py."""
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
