import re
import networkx as nx
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Xác định điểm đứt cáp", layout="wide")

# 1. Hàm tải dữ liệu
@st.cache_data
def load_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="uplink")
    df_cable = pd.read_excel(file_path, sheet_name="Đoạn cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")
    return df_uplink, df_cable, df_hdn

try:
    df_uplink, df_cable, df_hdn = load_data()
except Exception as e:
    st.error(f"Lỗi khi đọc file Data.xlsx: {e}")
    st.stop()

# Chuẩn hóa tên tập điểm (loại bỏ cổng, ví dụ TQGP001.011/HO/17 -> TQGP001.0011/HO)
def normalize_node(node_str):
    if pd.isna(node_str):
        return ""
    s = str(node_str).strip()
    s = re.sub(r'/\d+$', '', s)
    match = re.match(r'([A-Za-z0-9]+)\.(\d+)/([A-Za-z0-9]+)', s)
    if match:
        prefix, num, suffix = match.groups()
        return f"{prefix}.{int(num):04d}/{suffix}"
    return s

# 2. Xây dựng đồ thị từ sheet Đoạn cáp
G = nx.Graph()
for _, row in df_cable.iterrows():
    u = normalize_node(row['Điểm KN1'])
    v = normalize_node(row['Điểm KN2'])
    cable_name = str(row['Tên đoạn cáp']).strip()
    
    # Ép kiểu an toàn cho chiều dài
    try:
        length = float(row['Chiều dài thực (m)'])
    except (ValueError, TypeError):
        length = 0.0
        
    if u and v:
        G.add_edge(u, v, cable=cable_name, length=length)

# 3. Lấy tọa độ an toàn từ sheet HĐN (Xử lý dọn dẹp lỗi dữ liệu)
df_hdn['Lat_clean'] = pd.to_numeric(df_hdn['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
df_hdn['Lng_clean'] = pd.to_numeric(df_hdn['Lng'].astype(str).str.replace(',', '.'), errors='coerce')

hdn_coords = {}
for _, row in df_hdn.iterrows():
    name = normalize_node(row['Tên đối tượng'])
    lat = row['Lat_clean']
    lng = row['Lng_clean']
    if pd.notnull(lat) and pd.notnull(lng):
        hdn_coords[name] = (float(lat), float(lng))

st.title("📍 Xác Định Vị Trí Sự Cố Cáp Trên Bản Đồ")

# 4. Giao diện nhập liệu
col1, col2, col3 = st.columns(3)
with col1:
    td_a_input = st.text_input("Nhập TĐ A:", value="TQGP001.0011/HO")
with col2:
    td_b_input = st.text_input("Nhập TĐ B:", value="TQGP001.0013/HO")
with col3:
    target_dist = st.number_input("Khoảng cách từ TĐ A (mét):", min_value=0.0, value=100.0, step=1.0)

if st.button("Tìm vị trí sự cố"):
    td_a = normalize_node(td_a_input)
    td_b = normalize_node(td_b_input)

    if not td_a or not td_b:
        st.warning("Vui lòng nhập đầy đủ thông tin TĐ A và TĐ B!")
    elif not G.has_node(td_a) or not G.has_node(td_b):
        st.error("Một trong hai tập điểm nhập vào không tồn tại trong sheet Đoạn cáp!")
    elif not nx.has_path(G, td_a, td_b):
        st.error(f"Không tìm thấy đường đi giữa {td_a} và {td_b} trong dữ liệu Đoạn cáp!")
    else:
        node_path = nx.shortest_path(G, td_a, td_b, weight='length')
        
        cable_segments = []
        accumulated_dist = 0.0
        target_segment = None

        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i+1]
            edge_data = G[u][v]
            seg_len = edge_data['length']
            start_d = accumulated_dist
            accumulated_dist += seg_len
            
            seg_info = {
                'u': u,
                'v': v,
                'cable': edge_data['cable'],
                'length': seg_len,
                'start_dist': start_d,
                'end_dist': accumulated_dist
            }
            cable_segments.append(seg_info)

            if start_d <= target_dist <= accumulated_dist and target_segment is None:
                target_segment = seg_info

        st.info(f"Tổng chiều dài tuyến cáp từ {td_a} đến {td_b}: **{accumulated_dist:.1f} m**")

        if target_dist > accumulated_dist:
            st.error(f"Khoảng cách nhập vào ({target_dist}m) vượt quá tổng chiều dài tuyến cáp ({accumulated_dist:.1f}m)!")
        elif target_segment:
            st.success(f"Vị trí sự cố nằm trên đoạn cáp: **{target_segment['cable']}** (giữa {target_segment['u']} và {target_segment['v']})")

            u_coord = hdn_coords.get(target_segment['u'])
            v_coord = hdn_coords.get(target_segment['v'])

            if u_coord and v_coord:
                offset = target_dist - target_segment['start_dist']
                ratio = offset / target_segment['length'] if target_segment['length'] > 0 else 0
                
                fault_lat = u_coord[0] + ratio * (v_coord[0] - u_coord[0])
                fault_lng = u_coord[1] + ratio * (v_coord[1] - u_coord[1])

                m = folium.Map(location=[fault_lat, fault_lng], zoom_start=16)

                path_coords = [hdn_coords[n] for n in node_path if n in hdn_coords]
                if len(path_coords) > 1:
                    folium.PolyLine(path_coords, color="blue", weight=4, opacity=0.8, tooltip="Tuyến cáp").add_to(m)

                if td_a in hdn_coords:
                    folium.Marker(hdn_coords[td_a], popup=f"TĐ A: {td_a}", icon=folium.Icon(color="green")).add_to(m)
                if td_b in hdn_coords:
                    folium.Marker(hdn_coords[td_b], popup=f"TĐ B: {td_b}", icon=folium.Icon(color="black")).add_to(m)

                folium.Marker(
                    [fault_lat, fault_lng],
                    popup=f"Vị trí đứt cáp: {target_dist}m từ {td_a}",
                    icon=folium.Icon(color="red", icon="wrench", prefix="fa")
                ).add_to(m)

                st_folium(m, width=900, height=500)
            else:
                st.warning("Thiếu dữ liệu tọa độ Lat/Lng hợp lệ trong sheet HĐN cho đoạn cáp chứa vị trí đứt.")
