import streamlit as st
import requests
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import math

st.set_page_config(page_title="Florida SCIP Map Beast", layout="wide")
st.title("🗺️ Florida SCIP Map Beast 🌴🔥")
st.sidebar.header("Inputs")

geolocator = Nominatim(user_agent="scip_map_app")

location_input = st.sidebar.text_input("Location (address or lat,lon)", "Miami, FL")
radius_mi = st.sidebar.selectbox("Radius (miles)", [0.25, 0.50, 1.0], index=1)
radius_m = radius_mi * 1609.344

if st.sidebar.button("Generate Map 🚀"):
    with st.spinner("Building your SCIP beast..."):
        # Improved Geocode
        if "," in location_input.strip():
            try:
                parts = [p.strip() for p in location_input.split(",")]
                lat, lon = float(parts[0]), float(parts[1])
            except:
                st.error("Invalid lat,lon format 🤷 Try '25.7617, -80.1918'")
                st.stop()
        else:
            query = location_input.strip()
            if not query.lower().endswith(("florida", "fl")):
                query += ", Florida"
            loc = geolocator.geocode(query)
            if not loc:
                st.error("Address not found 🤷 Try more details or lat,lon")
                st.stop()
            lat, lon = loc.latitude, loc.longitude
        
        # Airports
        airports_url = "https://ourairports.com/data/airports.csv"
        df_airports = pd.read_csv(airports_url)
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        df_airports["dist"] = df_airports.apply(lambda row: haversine(lat, lon, row.latitude_deg, row.longitude_deg) if pd.notna(row.latitude_deg) else np.inf, axis=1)
        closest_airport = df_airports.loc[df_airports["dist"].idxmin()]
        
        # Build airport display with ICAO/IATA call letters and imperial distance
        ap_name = closest_airport["name"]
        ap_icao = closest_airport.get("ident", "N/A") or "N/A"
        ap_iata = closest_airport.get("iata_code", "N/A") or "N/A"
        ap_dist_mi = closest_airport["dist"] / 1609.344
        ap_label = f"{ap_name} ({ap_icao}"
        if str(ap_iata) not in ["N/A", "nan", ""] and str(ap_iata) != str(ap_icao):
            ap_label += f" / {ap_iata}"
        ap_label += ")"
        
        airports_js = f'L.marker([{closest_airport.latitude_deg}, {closest_airport.longitude_deg}]).bindTooltip("{ap_label}", {{permanent: true}}).bindPopup("<b>Closest Airport</b><br>{ap_name}<br>ICAO: {ap_icao}<br>IATA: {ap_iata}<br>Dist: {ap_dist_mi:.1f} mi").addTo(airportsLayer);\n'
        
        # Full HTML — basemaps use direct tile URLs, cell towers via HIFLD/FCC FeatureServer
        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SCIP Map - {location_input}</title>
            <meta charset="utf-8"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css"/>
            <style>#map {{height: 100vh;}}</style>
        </head>
        <body>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="https://unpkg.com/esri-leaflet@3.0.8/dist/esri-leaflet.js"></script>
            <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
            <script>
                var map = L.map('map').setView([{lat}, {lon}], 15);
                
                // Basemaps — direct tile URLs (replaces broken L.esri.basemapLayer from esri-leaflet v3)
                var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri World Imagery',
                    maxZoom: 19
                }});
                var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Topographic',
                    maxZoom: 19
                }});
                var streets = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Streets',
                    maxZoom: 19
                }});
                var usgsTopo = L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'USGS'
                }});
                
                var baseLayers = {{"Satellite": satellite, "Topographic": topo, "Streets": streets, "USGS Topo": usgsTopo}};
                
                // Overlays
                var overlays = {{}};
                var hillshade = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Hillshade',
                    opacity: 0.5
                }});
                overlays['Hillshading'] = hillshade;
                var transport = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Transportation',
                    opacity: 0.8
                }});
                overlays['Roads/Transport'] = transport;
                var labels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Labels',
                    opacity: 0.9
                }});
                overlays['Labels'] = labels;
                var flood = L.esri.dynamicMapLayer({{url: 'https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer', opacity: 0.5}});
                overlays['FEMA Flood Hazards'] = flood;
                
                // Wetlands — updated URL (old fwspub.wim.usgs.gov endpoint is dead)
                var wetlands = L.esri.dynamicMapLayer({{url: 'https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer', opacity: 0.6}});
                overlays['Wetlands (USFWS)'] = wetlands;
                
                var windSpeed = L.esri.tiledMapLayer({{url: 'https://gis.asce.org/arcgis/rest/services/ASCE722/w2022_Tile_RC_II/MapServer', opacity: 0.6}});
                overlays['ASCE 7 Wind Speed'] = windSpeed;
                
                var flParcels = L.esri.featureLayer({{
                    url: 'https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0',
                    style: {{color: '#ff7800', weight: 2, opacity: 0.8, fillOpacity: 0}},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var p = feature.properties;
                            var content = '<table><tr><td><b>Parcel ID:</b></td><td>' + (p.PARCEL_ID || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>Owner:</b></td><td>' + (p.OWN_NAME || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>Mailing:</b></td><td>' + (p.OWN_ADDR1 || '') + '<br>' + (p.OWN_CITY || '') + ', ' + (p.OWN_STATE || '') + ' ' + (p.OWN_ZIPCD || '') + '</td></tr>' +
                                          '<tr><td><b>Site Addr:</b></td><td>' + (p.PHY_ADDR1 || 'N/A') + '</td></tr>' +
                                          '<tr><td><b>DOR Use:</b></td><td>' + (p.DOR_UC || 'N/A') + '</td></tr></table>';
                            layer.bindPopup(content);
                            layer.bindTooltip(p.PARCEL_ID || 'Parcel', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['Florida Parcels (owner/details)'] = flParcels;
                
                // Cell Towers — HIFLD Cellular Towers FeatureServer (same FCC source data as AntennaSearch.com)
                var cellTowers = L.esri.featureLayer({{
                    url: 'https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Cellular_Towers_in_the_United_States/FeatureServer/0',
                    pointToLayer: function(feature, latlng) {{
                        return L.circleMarker(latlng, {{
                            radius: 7,
                            fillColor: '#ff0000',
                            color: '#333',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.8
                        }});
                    }},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var p = feature.properties;
                            var heightM = p.STRUC_HGT || p.OVRALL_HGT || null;
                            var heightFt = heightM ? (parseFloat(heightM) * 3.28084).toFixed(0) + ' ft' : 'N/A';
                            var content = '<table>' +
                                '<tr><td><b>Owner:</b></td><td>' + (p.LESSEE || p.LICENSEE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Structure Type:</b></td><td>' + (p.STRUC_TYPE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Height:</b></td><td>' + heightFt + '</td></tr>' +
                                '<tr><td><b>City/State:</b></td><td>' + (p.LOC_CITY || '') + ', ' + (p.LOC_STATE || '') + '</td></tr>' +
                                '<tr><td><b>FCC Reg #:</b></td><td>' + (p.REG_NUM || p.UNIQUE_SI || 'N/A') + '</td></tr>' +
                                '</table>';
                            layer.bindPopup(content);
                            layer.bindTooltip('Cell Tower', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['Cell Towers (HIFLD/FCC)'] = cellTowers;
                
                // FCC Antenna Structure Registration — registered structures 200ft+ or near airports
                var asrTowers = L.esri.featureLayer({{
                    url: 'https://services1.arcgis.com/Hp6G80Pez0CMNXhB/ArcGIS/rest/services/Antenna_Structure_Registration_ASR/FeatureServer/0',
                    pointToLayer: function(feature, latlng) {{
                        return L.circleMarker(latlng, {{
                            radius: 9,
                            fillColor: '#ff00ff',
                            color: '#333',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.7
                        }});
                    }},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var p = feature.properties;
                            var heightM = p.OVRALL_HGT || null;
                            var heightFt = heightM ? (parseFloat(heightM) * 3.28084).toFixed(0) + ' ft' : 'N/A';
                            var content = '<table>' +
                                '<tr><td><b>Owner:</b></td><td>' + (p.ENTITY || p.contname || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Structure Type:</b></td><td>' + (p.STRUC_TYPE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Overall Height:</b></td><td>' + heightFt + '</td></tr>' +
                                '<tr><td><b>City/State:</b></td><td>' + (p.CITY || '') + ', ' + (p.STATE || '') + '</td></tr>' +
                                '<tr><td><b>FCC ASR #:</b></td><td>' + (p.UNIQUE_SI || 'N/A') + '</td></tr>' +
                                '</table>';
                            layer.bindPopup(content);
                            layer.bindTooltip('FCC ASR Tower', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['FCC ASR Towers (AntennaSearch data)'] = asrTowers;
                
                var airportsLayer = L.layerGroup();
                overlays['Airports'] = airportsLayer;
                
                L.control.layers(baseLayers, overlays, {{collapsed: false}}).addTo(map);
                satellite.addTo(map);
                
                L.circle([{lat}, {lon}], {{radius: {radius_m}, color: 'yellow', weight: 3, fill: false}}).addTo(map);
                
                {airports_js}
                
                map.fitBounds(L.circle([{lat}, {lon}], {{radius: {radius_m}}}).getBounds().pad(0.5));
            </script>
        </body>
        </html>
        """
        
        st.components.v1.html(html_string, height=900, scrolling=True)
    st.success("Map loaded! Toggle layers top-right 👇")
