import streamlit as st
import requests
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import math
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Florida SCIP Map Beast", layout="wide")
st.title("🗺️ Florida SCIP Map Beast 🌴🔥")
st.sidebar.header("Inputs")

geolocator = Nominatim(user_agent="scip_map_app")

# TowerCoverage API credentials
TC_ACCOUNT = "56044"
TC_API_KEY = "062c78284ca0f7dc84b4e0ff5a4eebd5"

location_input = st.sidebar.text_input("Location (address or lat,lon)", "Miami, FL")
radius_mi = st.sidebar.selectbox("Radius (miles)", [0.25, 0.50, 1.0], index=1)
radius_m = radius_mi * 1609.344

# TowerCoverage Push Section
st.sidebar.markdown("---")
st.sidebar.subheader("Push to TowerCoverage")
tc_site_name = st.sidebar.text_input("Site Name", placeholder="e.g. Rockledge-01")
tc_site_height = st.sidebar.text_input("Tower Height (ft)", placeholder="e.g. 150")
tc_site_desc = st.sidebar.text_input("Description", placeholder="e.g. New candidate site")
tc_site_group = st.sidebar.text_input("Group", placeholder="e.g. Florida Sites")
push_to_tc = st.sidebar.button("Push to TowerCoverage 📡")

if push_to_tc:
    if not tc_site_name:
        st.sidebar.error("Site Name is required!")
    else:
        # Get coordinates from the location input
        push_lat, push_lon = None, None
        if "," in location_input.strip():
            try:
                parts = [p.strip() for p in location_input.split(",")]
                push_lat, push_lon = float(parts[0]), float(parts[1])
            except:
                st.sidebar.error("Invalid coordinates for push")
        else:
            query = location_input.strip()
            if not query.lower().endswith(("florida", "fl")):
                query += ", Florida"
            loc = geolocator.geocode(query)
            if loc:
                push_lat, push_lon = loc.latitude, loc.longitude

        if push_lat and push_lon:
            try:
                # Convert height from ft to meters for TC API
                height_m = str(round(float(tc_site_height) * 0.3048, 1)) if tc_site_height else "30"
                tc_url = "https://api.towercoverage.com/towercoverage.asmx/SitesAPI"
                tc_params = {
                    "Account": TC_ACCOUNT,
                    "Sitename": tc_site_name,
                    "Siteid": "",
                    "height": height_m,
                    "Latitude": str(push_lat),
                    "Longitude": str(push_lon),
                    "Description": tc_site_desc or "SCIP Map Beast candidate",
                    "Group": tc_site_group or "SCIP Sites",
                    "Pinstyle": "",
                    "key": TC_API_KEY
                }
                resp = requests.get(tc_url, params=tc_params, timeout=30)
                if resp.status_code == 200:
                    st.sidebar.success(f"Pushed '{tc_site_name}' to TowerCoverage!")
                else:
                    st.sidebar.error(f"Push failed: {resp.status_code}")
            except Exception as e:
                st.sidebar.error(f"Push error: {str(e)}")
        else:
            st.sidebar.error("Could not resolve coordinates for push")

if st.sidebar.button("Generate Map 🚀"):
    with st.spinner("Building your SCIP beast..."):
        # Geocode
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

        ap_name = closest_airport["name"]
        ap_icao = closest_airport.get("ident", "N/A") or "N/A"
        ap_iata = closest_airport.get("iata_code", "N/A") or "N/A"
        ap_dist_mi = closest_airport["dist"] / 1609.344
        ap_label = f"{ap_name} ({ap_icao}"
        if str(ap_iata) not in ["N/A", "nan", ""] and str(ap_iata) != str(ap_icao):
            ap_label += f" / {ap_iata}"
        ap_label += ")"

        airports_js = f'L.marker([{closest_airport.latitude_deg}, {closest_airport.longitude_deg}]).bindTooltip("{ap_label}", {{permanent: true}}).bindPopup("<b>Closest Airport</b><br>{ap_name}<br>ICAO: {ap_icao}<br>IATA: {ap_iata}<br>Dist: {ap_dist_mi:.1f} mi").addTo(airportsLayer);\n'

        # Pull TowerCoverage sites
        tc_sites_js = ""
        try:
            tc_resp = requests.get(
                "https://api.towercoverage.com/towercoverage.asmx/GetSiteList",
                params={"Account": TC_ACCOUNT, "key": TC_API_KEY},
                timeout=30
            )
            if tc_resp.status_code == 200:
                root = ET.fromstring(tc_resp.text)
                ns = {"tc": "http://tempuri.org/"}
                for site in root.findall("tc:Site", ns):
                    s_id = site.findtext("tc:siteid", "", ns)
                    s_name = site.findtext("tc:sitename", "", ns)
                    s_lat = site.findtext("tc:latitude", "", ns)
                    s_lon = site.findtext("tc:longitude", "", ns)
                    if s_lat and s_lon and s_id != "0":
                        tc_sites_js += f"""L.marker([{s_lat}, {s_lon}], {{
                            icon: L.divIcon({{
                                html: '<div style="background:#00e5ff;border:2px solid #fff;border-radius:50%;width:14px;height:14px;"></div>',
                                className: '',
                                iconSize: [14, 14],
                                iconAnchor: [7, 7]
                            }})
                        }}).bindTooltip("TC: {s_name}", {{sticky: true}}).bindPopup("<b>TowerCoverage Site</b><br>Name: {s_name}<br>ID: {s_id}").addTo(tcSitesLayer);\n"""
        except Exception as e:
            st.warning(f"TowerCoverage sites skipped: {str(e)}")

        # Full HTML
        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SCIP Map - {location_input}</title>
            <meta charset="utf-8"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css"/>
            <style>
                #map {{height: 100vh;}}
                .search-center-icon {{
                    background: #FFD700;
                    border: 3px solid #FF4500;
                    border-radius: 50%;
                    width: 20px;
                    height: 20px;
                    box-shadow: 0 0 10px rgba(255, 69, 0, 0.8), 0 0 20px rgba(255, 215, 0, 0.6);
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="https://unpkg.com/esri-leaflet@3.0.8/dist/esri-leaflet.js"></script>
            <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
            <script>
                var map = L.map('map').setView([{lat}, {lon}], 15);

                // Basemaps
                var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri World Imagery', maxZoom: 19
                }});
                var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Topographic', maxZoom: 19
                }});
                var streets = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Streets', maxZoom: 19
                }});
                var usgsTopo = L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'USGS'
                }});
                var baseLayers = {{"Satellite": satellite, "Topographic": topo, "Streets": streets, "USGS Topo": usgsTopo}};

                var overlays = {{}};

                // Reference overlays
                var hillshade = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Hillshade', opacity: 0.5
                }});
                overlays['Hillshading'] = hillshade;
                var transport = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Transportation', opacity: 0.8
                }});
                overlays['Roads/Transport'] = transport;
                var labels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Esri Labels', opacity: 0.9
                }});
                overlays['Labels'] = labels;

                // FEMA Flood
                var flood = L.esri.dynamicMapLayer({{url: 'https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer', opacity: 0.5}});
                overlays['FEMA Flood Hazards'] = flood;

                // Wetlands (updated URL)
                var wetlands = L.esri.dynamicMapLayer({{url: 'https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer', opacity: 0.6}});
                overlays['Wetlands (USFWS)'] = wetlands;

                // FCC Broadband / Fiber Availability
                var fccBroadband = L.esri.featureLayer({{
                    url: 'https://services.arcgis.com/jIL9msH9OI208GCb/ArcGIS/rest/services/FCC_BDC_June2024_CensusBlock/FeatureServer/0',
                    style: function(feature) {{
                        var fiber = feature.properties.fiber_prov_count || 0;
                        var color = fiber > 2 ? '#00ff00' : fiber > 0 ? '#ffff00' : '#ff0000';
                        return {{color: color, weight: 1, opacity: 0.5, fillOpacity: 0.3}};
                    }},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var p = feature.properties;
                            var content = '<b>FCC Broadband Data</b><br>' +
                                'Fiber Providers: ' + (p.fiber_prov_count || 0) + '<br>' +
                                'Cable Providers: ' + (p.cable_prov_count || 0) + '<br>' +
                                'Total BSLs: ' + (p.total_bsl || 'N/A') + '<br>' +
                                'Served: ' + (p.served || 'N/A') + '<br>' +
                                'Underserved: ' + (p.underserved || 'N/A') + '<br>' +
                                'Unserved: ' + (p.unserved || 'N/A');
                            layer.bindPopup(content);
                        }}
                    }}
                }});
                overlays['FCC Broadband/Fiber Availability'] = fccBroadband;

                // Florida Parcels
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

                // Cell Towers (HIFLD/FCC) - RED markers
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
                            var content = '<b style="color:#ff0000;">&#x25CF; Cell Tower (HIFLD/FCC)</b><br><table>' +
                                '<tr><td><b>Owner:</b></td><td>' + (p.LESSEE || p.LICENSEE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Type:</b></td><td>' + (p.STRUC_TYPE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Height:</b></td><td>' + heightFt + '</td></tr>' +
                                '<tr><td><b>City/State:</b></td><td>' + (p.LOC_CITY || '') + ', ' + (p.LOC_STATE || '') + '</td></tr>' +
                                '<tr><td><b>FCC Reg #:</b></td><td>' + (p.REG_NUM || p.UNIQUE_SI || 'N/A') + '</td></tr></table>';
                            layer.bindPopup(content);
                            layer.bindTooltip('Cell Tower', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['\\U0001f534 Cell Towers (HIFLD/FCC)'] = cellTowers;

                // FCC ASR Towers / Antennas - MAGENTA markers
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
                            var content = '<b style="color:#ff00ff;">&#x25CF; FCC ASR Antenna/Tower</b><br><table>' +
                                '<tr><td><b>Owner:</b></td><td>' + (p.ENTITY || p.contname || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Type:</b></td><td>' + (p.STRUC_TYPE || 'N/A') + '</td></tr>' +
                                '<tr><td><b>Height:</b></td><td>' + heightFt + '</td></tr>' +
                                '<tr><td><b>City/State:</b></td><td>' + (p.CITY || '') + ', ' + (p.STATE || '') + '</td></tr>' +
                                '<tr><td><b>FCC ASR #:</b></td><td>' + (p.UNIQUE_SI || 'N/A') + '</td></tr></table>';
                            layer.bindPopup(content);
                            layer.bindTooltip('FCC ASR Antenna', {{sticky: true}});
                        }}
                    }}
                }});
                overlays['\\U0001f7ea FCC ASR Antennas (AntennaSearch)'] = asrTowers;

                // TowerCoverage Sites - CYAN markers
                var tcSitesLayer = L.layerGroup();
                overlays['\\U0001f535 TowerCoverage Sites'] = tcSitesLayer;

                // Airports
                var airportsLayer = L.layerGroup();
                overlays['Airports'] = airportsLayer;

                L.control.layers(baseLayers, overlays, {{collapsed: false}}).addTo(map);
                satellite.addTo(map);

                // Search Ring
                L.circle([{lat}, {lon}], {{radius: {radius_m}, color: 'yellow', weight: 3, fill: false}}).addTo(map);

                // Search Ring Center - GOLD/ORANGE star marker
                var centerIcon = L.divIcon({{
                    html: '<div class="search-center-icon"></div>',
                    className: '',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                }});
                L.marker([{lat}, {lon}], {{icon: centerIcon}}).bindTooltip("SEARCH CENTER", {{permanent: true, direction: 'top', offset: [0, -12]}}).bindPopup("<b>Search Ring Center</b><br>Lat: {lat}<br>Lon: {lon}<br>Radius: {radius_mi} mi").addTo(map);

                {airports_js}
                {tc_sites_js}

                map.fitBounds(L.circle([{lat}, {lon}], {{radius: {radius_m}}}).getBounds().pad(0.5));
            </script>
        </body>
        </html>
        """

        st.components.v1.html(html_string, height=900, scrolling=True)
    st.success("Map loaded! Toggle layers top-right 👇")
