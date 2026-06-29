from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                                 QLabel, QComboBox, QFileDialog, QMessageBox, 
                                 QProgressBar, QGroupBox, QTextEdit)
from qgis.PyQt.QtCore import Qt
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, 
                       QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem)
from qgis.utils import iface
import csv
import os
import processing

class ExtractorAlturasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extractor de Alturas desde DTM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Grupo de capas
        grupo_capas = QGroupBox("Selección de Capas")
        layout_capas = QVBoxLayout()
        
        # Selector de capa de puntos (vértices)
        layout_puntos = QHBoxLayout()
        label_puntos = QLabel("Capa de Vértices:")
        self.combo_puntos = QComboBox()
        self.cargar_capas_vectoriales()
        layout_puntos.addWidget(label_puntos)
        layout_puntos.addWidget(self.combo_puntos)
        layout_capas.addLayout(layout_puntos)
        
        # Selector de capa DTM
        layout_dtm = QHBoxLayout()
        label_dtm = QLabel("Capa DTM (Raster):")
        self.combo_dtm = QComboBox()
        self.cargar_capas_raster()
        layout_dtm.addWidget(label_dtm)
        layout_dtm.addWidget(self.combo_dtm)
        layout_capas.addLayout(layout_dtm)
        
        grupo_capas.setLayout(layout_capas)
        layout.addWidget(grupo_capas)
        
        # Grupo de archivo de salida
        grupo_salida = QGroupBox("Archivo de Salida")
        layout_salida = QVBoxLayout()
        
        layout_archivo = QHBoxLayout()
        self.label_archivo = QLabel("No seleccionado")
        self.btn_seleccionar = QPushButton("Seleccionar CSV")
        self.btn_seleccionar.clicked.connect(self.seleccionar_archivo)
        layout_archivo.addWidget(self.label_archivo)
        layout_archivo.addWidget(self.btn_seleccionar)
        layout_salida.addLayout(layout_archivo)
        
        grupo_salida.setLayout(layout_salida)
        layout.addWidget(grupo_salida)
        
        # Log de diagnóstico
        grupo_log = QGroupBox("Log de Proceso")
        layout_log = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout_log.addWidget(self.log_text)
        grupo_log.setLayout(layout_log)
        layout.addWidget(grupo_log)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Botones de acción
        layout_botones = QHBoxLayout()
        self.btn_procesar = QPushButton("Procesar")
        self.btn_procesar.clicked.connect(self.procesar)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.close)
        layout_botones.addWidget(self.btn_procesar)
        layout_botones.addWidget(self.btn_cerrar)
        layout.addLayout(layout_botones)
        
        self.setLayout(layout)
        
    def log(self, mensaje):
        """Agrega mensaje al log"""
        self.log_text.append(mensaje)
        
    def cargar_capas_vectoriales(self):
        """Carga todas las capas vectoriales de puntos del proyecto"""
        self.combo_puntos.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 0:  # 0 = Punto
                self.combo_puntos.addItem(layer.name(), layer)
                
    def cargar_capas_raster(self):
        """Carga todas las capas raster del proyecto"""
        self.combo_dtm.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsRasterLayer):
                self.combo_dtm.addItem(layer.name(), layer)
                
    def seleccionar_archivo(self):
        """Abre diálogo para seleccionar archivo CSV de salida"""
        archivo, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar CSV", 
            "", 
            "CSV Files (*.csv)"
        )
        if archivo:
            if not archivo.endswith('.csv'):
                archivo += '.csv'
            self.archivo_salida = archivo
            self.label_archivo.setText(os.path.basename(archivo))
            
    def procesar(self):
        """Procesa la extracción de alturas"""
        self.log_text.clear()
        
        # Validaciones
        if self.combo_puntos.count() == 0:
            QMessageBox.warning(self, "Error", "No hay capas de puntos disponibles")
            return
            
        if self.combo_dtm.count() == 0:
            QMessageBox.warning(self, "Error", "No hay capas raster disponibles")
            return
            
        if not hasattr(self, 'archivo_salida'):
            QMessageBox.warning(self, "Error", "Seleccione un archivo de salida")
            return
            
        # Obtener capas seleccionadas
        capa_puntos = self.combo_puntos.currentData()
        capa_dtm = self.combo_dtm.currentData()
        
        if not capa_puntos or not capa_dtm:
            QMessageBox.warning(self, "Error", "Seleccione las capas correctamente")
            return
        
        # Información de diagnóstico
        self.log(f"=== INFORMACIÓN DE CAPAS ===")
        self.log(f"Capa de puntos: {capa_puntos.name()}")
        self.log(f"CRS puntos: {capa_puntos.crs().authid()}")
        self.log(f"Total puntos: {capa_puntos.featureCount()}")
        self.log(f"\nCapa DTM: {capa_dtm.name()}")
        self.log(f"CRS DTM: {capa_dtm.crs().authid()}")
        self.log(f"Extensión DTM: {capa_dtm.extent().toString()}")
        self.log(f"Válido: {capa_dtm.isValid()}")
        
        # Verificar si es necesaria transformación de coordenadas
        transformar = False
        transform = None
        if capa_puntos.crs() != capa_dtm.crs():
            transformar = True
            transform = QgsCoordinateTransform(
                capa_puntos.crs(), 
                capa_dtm.crs(), 
                QgsProject.instance()
            )
            self.log(f"\n⚠ Los CRS son diferentes. Se aplicará transformación.")
        else:
            self.log(f"\n✓ Los CRS coinciden.")
            
        # Configurar barra de progreso
        total_features = capa_puntos.featureCount()
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total_features)
        self.progress_bar.setValue(0)
        
        # Procesar puntos
        resultados = []
        contador = 0
        exitosos = 0
        fallidos = 0
        
        self.log(f"\n=== PROCESANDO PUNTOS ===")
        
        try:
            for feature in capa_puntos.getFeatures():
                contador += 1
                self.progress_bar.setValue(contador)
                
                # Obtener geometría del punto
                geom = feature.geometry()
                if geom.isMultipart():
                    punto = geom.asMultiPoint()[0]
                else:
                    punto = geom.asPoint()
                
                # Transformar si es necesario
                punto_dtm = QgsPointXY(punto)
                if transformar:
                    punto_dtm = transform.transform(punto)
                
                # Extraer coordenadas originales
                este = punto.x()
                norte = punto.y()
                
                # Extraer altura del DTM (método mejorado)
                altura = self.extraer_altura_dtm_mejorado(capa_dtm, punto_dtm)
                
                if altura is not None:
                    exitosos += 1
                    if exitosos <= 3:  # Mostrar solo los primeros 3
                        self.log(f"✓ Punto {contador}: Altura = {altura:.3f} m")
                else:
                    fallidos += 1
                    if fallidos <= 3:  # Mostrar solo los primeros 3 fallos
                        self.log(f"✗ Punto {contador}: Sin valor")
                
                # Obtener ID
                id_punto = self.obtener_id(feature)
                
                # Formatear coordenadas a 3 decimales
                este_fmt = f"{este:.3f}"
                norte_fmt = f"{norte:.3f}"
                altura_fmt = f"{altura:.3f}" if altura is not None else "N/A"
                
                # Agregar resultado
                resultados.append({
                    'id': id_punto,
                    'este': este_fmt,
                    'norte': norte_fmt,
                    'altura_ortometrica': altura_fmt,
                    'descripcion': 'VERTICE'
                })
            
            # Escribir CSV
            self.escribir_csv(resultados)
            
            self.progress_bar.setVisible(False)
            
            self.log(f"\n=== RESUMEN ===")
            self.log(f"Total procesados: {contador}")
            self.log(f"Exitosos: {exitosos}")
            self.log(f"Fallidos: {fallidos}")
            self.log(f"Archivo guardado: {self.archivo_salida}")
            
            if fallidos > 0:
                QMessageBox.warning(
                    self, 
                    "Proceso Completado con Advertencias", 
                    f"Se procesaron {contador} puntos.\n"
                    f"Exitosos: {exitosos}\n"
                    f"Sin valor: {fallidos}\n\n"
                    f"Revisa el log para más detalles."
                )
            else:
                QMessageBox.information(
                    self, 
                    "Éxito", 
                    f"Se procesaron {contador} puntos correctamente.\n"
                    f"Archivo guardado en:\n{self.archivo_salida}"
                )
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.log(f"\n✗✗✗ ERROR: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al procesar: {str(e)}")
            
    def extraer_altura_dtm_mejorado(self, capa_dtm, punto):
        """Extrae la altura del DTM usando múltiples métodos"""
        # Método 1: Identificación directa
        try:
            resultado = capa_dtm.dataProvider().identify(
                punto, 
                QgsRasterLayer.IdentifyFormatValue
            )
            
            if resultado.isValid():
                valores = resultado.results()
                if valores:
                    altura = list(valores.values())[0]
                    if altura is not None:
                        # Verificar si es un valor NoData
                        nodata = capa_dtm.dataProvider().sourceNoDataValue(1)
                        if altura != nodata and str(altura).lower() != 'nan':
                            return float(altura)
        except Exception as e:
            pass
        
        # Método 2: Muestreo directo (más robusto)
        try:
            valor = capa_dtm.dataProvider().sample(punto, 1)[0]
            if valor is not None and str(valor).lower() != 'nan':
                return float(valor)
        except:
            pass
            
        return None
            
    def obtener_id(self, feature):
        """Obtiene el ID del feature, intentando varios campos comunes"""
        campos_id = ['id', 'ID', 'fid', 'FID', 'objectid', 'OBJECTID', 'gid', 'GID']
        
        # Intentar con campos comunes
        for campo in campos_id:
            if campo in feature.fields().names():
                return str(feature[campo])
        
        # Si no encuentra, usar el ID del feature
        return str(feature.id())
        
    def escribir_csv(self, resultados):
        """Escribe los resultados en un archivo CSV"""
        with open(self.archivo_salida, 'w', newline='', encoding='utf-8') as csvfile:
            campos = ['id', 'este', 'norte', 'altura_ortometrica', 'descripcion']
            writer = csv.DictWriter(csvfile, fieldnames=campos)
            
            writer.writeheader()
            writer.writerows(resultados)

# Función para ejecutar el diálogo
def ejecutar_extractor():
    dialog = ExtractorAlturasDialog(iface.mainWindow())
    dialog.exec_()

# Ejecutar
ejecutar_extractor()
