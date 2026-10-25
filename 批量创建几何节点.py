bl_info = {
    "name": "几何节点批量添加工具(JSON外部配置)",
    "author": "",
    "version": (1, 9),
    "blender": (5, 2, 0),
    "location": "几何节点编辑器 → N面板 → GeoNode批量添加",
    "description": "外部JSON加载树形菜单，批量创建几何节点，中文显示，搜索，展开折叠，重载配置",
    "category": "Node",
}

import bpy
import random
import json
import os

# ===================== 配置 =====================
JSON_FILENAME = "geonode_menu.json"
# ===============================================

def load_menu_from_json():
    """从同目录json加载菜单树"""
    script_path = bpy.context.space_data.text.filepath
    if not script_path:
        raise Exception("请先保存当前文本文件到磁盘，才能读取JSON！")
    dir_path = os.path.dirname(script_path)
    json_path = os.path.join(dir_path, JSON_FILENAME)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def collect_nodes_and_menus(menu_content, parent_path="", node_items=None, id_to_chinese=None, menu_paths=None):
    """递归收集节点列表、ID映射、菜单路径"""
    if node_items is None:
        node_items = []
    if id_to_chinese is None:
        id_to_chinese = {}
    if menu_paths is None:
        menu_paths = []

    if isinstance(menu_content, dict):
        for menu_name, sub_content in menu_content.items():
            current_path = f"{parent_path}_{menu_name}"
            menu_paths.append(current_path)
            collect_nodes_and_menus(sub_content, current_path, node_items, id_to_chinese, menu_paths)
    elif isinstance(menu_content, list):
        for node_id, chn_name in menu_content:
            node_items.append(node_id)
            id_to_chinese[node_id] = chn_name
    return node_items, id_to_chinese, menu_paths


# -------------------------- Operators --------------------------
class GEO_OT_ReloadJson(bpy.types.Operator):
    bl_idname = "geo.reload_json_menu"
    bl_label = "重载JSON菜单配置"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 重新加载json并重建全局变量
        global MENU_CONFIG, ALL_NODE_ITEMS, NODE_ID_TO_CHN, MENU_PATH_LIST
        try:
            MENU_CONFIG = load_menu_from_json()
            ALL_NODE_ITEMS, NODE_ID_TO_CHN, MENU_PATH_LIST = collect_nodes_and_menus(MENU_CONFIG)
            self.report({'INFO'}, "JSON菜单配置重载成功！请重新运行脚本注册属性。")
        except Exception as e:
            self.report({'ERROR'}, f"读取JSON失败: {str(e)}")
        return {'FINISHED'}


class GEO_OT_BatchAddGeoNodes(bpy.types.Operator):
    bl_idname = "geo.batch_add_geonodes"
    bl_label = "批量创建勾选节点"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        space = context.space_data
        if space.type != 'NODE_EDITOR' or space.tree_type != 'GeometryNodeTree':
            self.report({'WARNING'}, "请切换到【几何节点编辑器】再执行！")
            return {'CANCELLED'}
        node_tree = space.node_tree
        if not node_tree:
            self.report({'WARNING'}, "当前没有几何节点树")
            return {'CANCELLED'}

        settings = context.scene.geo_node_add_settings
        menu_node_map = {}

        def scan_nodes(menu_name, menu_content):
            if isinstance(menu_content, list):
                for node_id, chn_name in menu_content:
                    if getattr(settings, f"node_check_{node_id}"):
                        if menu_name not in menu_node_map:
                            menu_node_map[menu_name] = []
                        menu_node_map[menu_name].append(node_id)
            elif isinstance(menu_content, dict):
                for sub_name, sub_content in menu_content.items():
                    scan_nodes(sub_name, sub_content)

        scan_nodes("root", MENU_CONFIG)

        if len(menu_node_map) == 0:
            self.report({'INFO'}, "没有勾选任何节点")
            return {'CANCELLED'}

        step_x = settings.step_x
        step_y = settings.step_y
        use_horizontal = settings.sort_horizontal

        for frame_name, node_id_list in menu_node_map.items():
            frame = node_tree.nodes.new(type='NodeFrame')
            frame.label = frame_name
            offset_x = 0
            offset_y = 0
            for node_id in node_id_list:
                new_node = node_tree.nodes.new(type=node_id)
                new_node.location = (offset_x, offset_y)
                new_node.parent = frame

                use_color = getattr(settings, f"node_use_color_{node_id}")
                if use_color:
                    node_col = getattr(settings, f"node_color_{node_id}")
                    new_node.use_custom_color = True
                    new_node.color = node_col
                else:
                    new_node.use_custom_color = False

                if use_horizontal:
                    offset_x += step_x
                else:
                    offset_y += step_y

        self.report({'INFO'}, f"成功创建节点，共 {len(menu_node_map)} 个分组Frame")
        return {'FINISHED'}


class GEO_OT_SelectAllNodes(bpy.types.Operator):
    bl_idname = "geo.select_all_nodes"
    bl_label = "全选节点"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        settings = context.scene.geo_node_add_settings
        for node_id in ALL_NODE_ITEMS:
            setattr(settings, f"node_check_{node_id}", True)
        return {'FINISHED'}


class GEO_OT_DeselectAllNodes(bpy.types.Operator):
    bl_idname = "geo.deselect_all_nodes"
    bl_label = "清空选择"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        settings = context.scene.geo_node_add_settings
        for node_id in ALL_NODE_ITEMS:
            setattr(settings, f"node_check_{node_id}", False)
        return {'FINISHED'}


class GEO_OT_InvertSelectNodes(bpy.types.Operator):
    bl_idname = "geo.invert_select_nodes"
    bl_label = "反选节点"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        settings = context.scene.geo_node_add_settings
        for node_id in ALL_NODE_ITEMS:
            val = getattr(settings, f"node_check_{node_id}")
            setattr(settings, f"node_check_{node_id}", not val)
        return {'FINISHED'}


class GEO_OT_ExpandAllMenus(bpy.types.Operator):
    bl_idname = "geo.expand_all_menus"
    bl_label = "全部展开"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        settings = context.scene.geo_node_add_settings
        for menu_key in MENU_PATH_LIST:
            setattr(settings, f"expand_{menu_key}", True)
        return {'FINISHED'}


class GEO_OT_CollapseAllMenus(bpy.types.Operator):
    bl_idname = "geo.collapse_all_menus"
    bl_label = "全部折叠"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        settings = context.scene.geo_node_add_settings
        for menu_key in MENU_PATH_LIST:
            setattr(settings, f"expand_{menu_key}", False)
        return {'FINISHED'}


# -------------------------- Panel UI --------------------------
class GEO_PT_GeoNodeBatchPanel(bpy.types.Panel):
    bl_label = "GeoNode批量添加"
    bl_idname = "GEO_PT_GeoNodeBatchPanel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GeoNode批量添加'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geo_node_add_settings
        keyword = settings.search_keyword.lower()

        box_top = layout.box()
        box_top.operator("geo.reload_json_menu", icon='FILE_REFRESH', text="重载JSON配置")
        box_top.operator("geo.batch_add_geonodes", text="✅ 创建勾选节点", icon='ADD')

        row_ops = box_top.row(align=True)
        row_ops.operator("geo.select_all_nodes", text="全选")
        row_ops.operator("geo.invert_select_nodes", text="反选")
        row_ops.operator("geo.deselect_all_nodes", text="清空")

        row_menu_toggle = box_top.row(align=True)
        row_menu_toggle.operator("geo.expand_all_menus", text="全部展开")
        row_menu_toggle.operator("geo.collapse_all_menus", text="全部折叠")

        box_top.prop(settings, "search_keyword", icon='VIEWZOOM')

        row = box_top.row()
        row.prop(settings, "sort_horizontal")
        row.prop(settings, "show_count")

        row_step = box_top.row()
        row_step.prop(settings, "step_x")
        row_step.prop(settings, "step_y")

        if settings.show_count:
            count = 0
            for node_id in ALL_NODE_ITEMS:
                if getattr(settings, f"node_check_{node_id}"):
                    count +=1
            box_top.label(text=f"✅ 已勾选节点总数：{count}")

        def draw_menu(parent_layout, menu_name, menu_content, parent_key=""):
            menu_key = f"{parent_key}_{menu_name}"
            expand_prop = f"expand_{menu_key}"

            has_match = False
            if isinstance(menu_content, list):
                for node_id, chn_name in menu_content:
                    if keyword in node_id.lower() or keyword in chn_name.lower():
                        has_match = True
            elif isinstance(menu_content, dict):
                for sub_name, sub_content in menu_content.items():
                    if isinstance(sub_content, list):
                        for nid, chn_name in sub_content:
                            if keyword in nid.lower() or keyword in chn_name.lower():
                                has_match = True
                                break
            if keyword and not has_match:
                return

            row = parent_layout.row(align=True)
            row.prop(settings, expand_prop, text=menu_name, icon='TRIA_DOWN' if getattr(settings, expand_prop) else 'TRIA_RIGHT')

            if getattr(settings, expand_prop):
                box = parent_layout.box()
                if isinstance(menu_content, dict):
                    for sub_name, sub_content in menu_content.items():
                        draw_menu(box, sub_name, sub_content, menu_key)
                elif isinstance(menu_content, list):
                    for node_id, chn_name in menu_content:
                        if not (keyword in node_id.lower() or keyword in chn_name.lower()):
                            continue
                        row_node = box.row(align=True)
                        row_node.prop(settings, f"node_check_{node_id}", text=chn_name)
                        row_node.prop(settings, f"node_use_color_{node_id}", text="")
                        if getattr(settings, f"node_use_color_{node_id}"):
                            row_node.prop(settings, f"node_color_{node_id}", text="")

        for top_menu_name, sub_content in MENU_CONFIG.items():
            draw_menu(layout, top_menu_name, sub_content)


# -------------------------- Register --------------------------
classes = [
    GEO_OT_ReloadJson,
    GEO_OT_BatchAddGeoNodes,
    GEO_OT_SelectAllNodes,
    GEO_OT_DeselectAllNodes,
    GEO_OT_InvertSelectNodes,
    GEO_OT_ExpandAllMenus,
    GEO_OT_CollapseAllMenus,
    GEO_PT_GeoNodeBatchPanel
]

def register():
    global MENU_CONFIG, ALL_NODE_ITEMS, NODE_ID_TO_CHN, MENU_PATH
    MENU_CONFIG = load_menu_from_json()
    ALL_NODE_ITEMS, NODE_ID_TO_CHN, MENU_PATH_LIST = collect_nodes_and_menus(MENU_CONFIG)

    # 动态构建属性组
    prop_vars = {}
    for node_id in ALL_NODE_ITEMS:
        r = random.uniform(0.25,0.75)
        g = random.uniform(0.25,0.75)
        b = random.uniform(0.25,0.75)
        prop_vars[f"node_check_{node_id}"] = bpy.props.BoolProperty(default=False)
        prop_vars[f"node_use_color_{node_id}"] = bpy.props.BoolProperty(default=False)
        prop_vars[f"node_color_{node_id}"] = bpy.props.FloatVectorProperty(subtype='COLOR',min=0,max=1,default=(r,g,b))
    for menu_key in MENU_PATH_LIST:
        prop_vars[f"expand_{menu_key}"] = bpy.props.BoolProperty(default=False)

    class GeoNodeAddSettings(bpy.types.PropertyGroup):
        sort_horizontal: bpy.props.BoolProperty(name="水平排序", default=True)
        show_count: bpy.props.BoolProperty(name="显示勾选数量统计", default=True)
        search_keyword: bpy.props.StringProperty(name="搜索", default="")
        step_x: bpy.props.IntProperty(name="水平间距", default=180, min=50, max=800)
        step_y: bpy.props.IntProperty(name="垂直间距", default=-200, min=-800, max=-50)
        locals().update(prop_vars)

    bpy.utils.register_class(GeoNodeAddSettings)
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.geo_node_add_settings = bpy.props.PointerProperty(type=GeoNodeAddSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(GeoNodeAddSettings)
    del bpy.types.Scene.geo_node_add_settings


if __name__ == "__main__":
    register()
