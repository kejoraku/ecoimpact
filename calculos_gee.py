import ee

def obtener_todas_las_capas_gee(anio):
    """Calcula los 4 índices ambientales para Argentina en un único flujo de GEE."""
    fecha_inicio, fecha_fin = f"{anio}-01-01", f"{anio}-12-31"
    
    try:
        # Asegúrate de mantener tu ID de proyecto de Google Cloud funcionando aquí
        ee.Initialize(project='ee-raanidg')
    except:
        pass

    argentina_roi = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Argentina"))
    urls_capas = {}
    usa_sentinel = True
    
    try:
        coleccion = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                        .filterDate(fecha_inicio, fecha_fin) \
                        .filterBounds(argentina_roi) \
                        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        if coleccion.size().getInfo() == 0:
            usa_sentinel = False
        else:
            imagen = coleccion.median().clip(argentina_roi)
    except:
        usa_sentinel = False

    if not usa_sentinel:
        try:
            coleccion = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                            .filterDate(fecha_inicio, fecha_fin) \
                            .filterBounds(argentina_roi) \
                            .filter(ee.Filter.lt('CLOUD_COVER', 20))
            imagen = coleccion.median().clip(argentina_roi)
        except:
            return urls_capas, "Error satelital"

    try:
        b3, b4, b2 = imagen.select('B3'), imagen.select('B4'), imagen.select('B2')
        osi = (b3.add(b4)).divide(b2)
        urls_capas["OSI"] = osi.getMapId({'min': 1.0, 'max': 3.0, 'palette': ['#2c3e50', '#7f8c8d', '#111111']})['tile_fetcher'].url_format

        bandas_ndwi = ['B3', 'B8'] if usa_sentinel else ['B3', 'B5']
        ndwi = imagen.normalizedDifference(bandas_ndwi)
        urls_capas["NDWI"] = ndwi.getMapId({'min': -0.5, 'max': 0.5, 'palette': ['#7fffd4', '#1e90ff', '#00008b']})['tile_fetcher'].url_format

        bandas_nbri = ['B8', 'B12'] if usa_sentinel else ['SR_B5', 'SR_B7']
        nbri = imagen.normalizedDifference(bandas_nbri)
        urls_capas["NBRI"] = nbri.getMapId({'min': -0.4, 'max': 0.6, 'palette': ['#ff4500', '#ffa500', '#ffff00', '#008000']})['tile_fetcher'].url_format

        bandas_ndsi = ['B3', 'B11'] if usa_sentinel else ['SR_B3', 'SR_B6']
        ndsi = imagen.normalizedDifference(bandas_ndsi)
        urls_capas["NDSI"] = ndsi.getMapId({'min': 0.0, 'max': 0.8, 'palette': ['#ffffff', '#afeeee', '#00ffff']})['tile_fetcher'].url_format

        return urls_capas, "Sentinel-2" if usa_sentinel else "Landsat 8"
    except Exception as e:
        return urls_capas, f"Error en bandas: {e}"
