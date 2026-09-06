# 7. BẢN ĐỒ FULL TRÀN VIỀN BÊN PHẢI
if map_data:
    # 1. Khởi tạo bản đồ với tiles=None để loại bỏ lớp nền OSM mặc định
    m = folium.Map(
        location=[map_data['fault_lat'], map_data['fault_lng']], 
        zoom_start=17,
        tiles=None
    )

    # 2. Thêm Layer Google Maps Đường phố (Sẽ đóng vai trò làm nền mặc định)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Đường phố",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. Thêm Layer Google Maps Vệ tinh
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Vệ tinh",
        overlay=False,
        control=True
    ).add_to(m)

    # Nút định vị GPS thực tế
    LocateControl(auto_start=False, flyTo=True).add_to(m)
    folium.LayerControl().add_to(m)

    # Vẽ Tuyến cáp
    path_coords = [hdn_coords[n] for n in map_data['node_path'] if n in hdn_coords]
    if len(path_coords) > 1:
        folium.PolyLine(path_coords, color="#1e40af", weight=6, opacity=0.85, tooltip="Tuyến cáp").add_to(m)

    # Marker TĐ A và TĐ B
    if map_data['td_a'] in hdn_coords:
        folium.Marker(hdn_coords[map_data['td_a']], popup=f"TĐ A: {map_data['td_a']}", icon=folium.Icon(color="green")).add_to(m)
    if map_data['td_b'] in hdn_coords:
        folium.Marker(hdn_coords[map_data['td_b']], popup=f"TĐ B: {map_data['td_b']}", icon=folium.Icon(color="black")).add_to(m)

    # Marker Điểm Đứt Cáp
    folium.Marker(
        [map_data['fault_lat'], map_data['fault_lng']],
        popup=f"Vị trí đứt cáp: {map_data['target_dist']}m từ {map_data['td_a']}",
        icon=folium.Icon(color="red", icon="wrench", prefix="fa")
    ).add_to(m)

    st_folium(m, width="100%", height=1000, key="fault_map")

else:
    # Bản đồ mặc định ban đầu khi chưa bấm tìm kiếm
    default_map = folium.Map(
        location=[21.0285, 105.8542],
        zoom_start=12,
        tiles=None
    )
    
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Đường phố",
        overlay=False,
        control=False
    ).add_to(default_map)
    
    LocateControl(auto_start=False, flyTo=True).add_to(default_map)
    st_folium(default_map, width="100%", height=1000, key="default_map")
