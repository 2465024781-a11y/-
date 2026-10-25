import bpy

def rename_cameras_by_timeline_order():
    """按时间线标记顺序重命名摄像机"""
    
    scene = bpy.context.scene
    
    # 获取所有标记
    markers = scene.timeline_markers
    
    if not markers:
        print("时间线上没有标记")
        return
    
    # 按帧号排序标记
    sorted_markers = sorted(markers, key=lambda m: m.frame)
    
    # 存储已处理的摄像机，避免重复命名
    processed_cameras = set()
    camera_index = 1
    
    for marker in sorted_markers:
        # 获取标记绑定的摄像机
        camera = marker.camera
        
        if camera is None:
            print(f"标记 '{marker.name}' (帧 {marker.frame}) 没有绑定摄像机，跳过")
            continue
        
        # 检查是否已经处理过这个摄像机
        if camera.name in processed_cameras:
            print(f"摄像机 '{camera.name}' 已在更早的标记中出现，跳过")
            continue
        
        # 生成新名称
        new_name = f"Camera_{camera_index:03d}"
        
        # 重命名摄像机
        old_name = camera.name
        camera.name = new_name
        processed_cameras.add(new_name)
        
        print(f"重命名: '{old_name}' -> '{new_name}' (帧 {marker.frame})")
        camera_index += 1
    
    print(f"完成！共重命名了 {camera_index - 1} 个摄像机")

# 执行重命名
rename_cameras_by_timeline_order()