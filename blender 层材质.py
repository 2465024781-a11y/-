bl_info = {
    "name": "VRay‑Like Blend Material Layers",
    "author": "v2.3 Toggle Displacement Socket",
    "version": (2, 3),
    "blender": (3, 4, 0),
    "location": "Shader Editor → N‑Panel → BlendLayers",
    "description": "Add layer group node to CURRENT material, toggle create displacement sockets. Layer list at bottom.",
    "category": "Node",
}

import bpy

GROUP_NAME = "BlendMaterialStack"


class BlendLayerSettings(bpy.types.PropertyGroup):
    layer_list: bpy.props.StringProperty(default="0,1")
    active_layer: bpy.props.IntProperty(default=1)
    use_displacement: bpy.props.BoolProperty(
        name="Use Displacement",
        description="Generate displacement input sockets and displacement mixing chain",
        default=True,
        update=lambda self,ctx: rebuild_group(get_group())
    )


def get_socket_by_name(node, socket_name):
    for sock in node.outputs:
        if sock.name == socket_name:
            return sock
    for sock in node.inputs:
        if sock.name == socket_name:
            return sock
    return None


def list_to_str(lst):
    return ",".join(str(x) for x in lst)


def str_to_list(s):
    if not s:
        return [0]
    return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]


def get_group():
    if GROUP_NAME not in bpy.data.node_groups:
        g = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
        settings = bpy.context.scene.blend_layer_settings
        settings.layer_list = "0,1"
        settings.active_layer = 1
        rebuild_group(g)
    return bpy.data.node_groups[GROUP_NAME]


def rebuild_group(group):
    nodes = group.nodes
    links = group.links
    nodes.clear()
    links.clear()

    for sock in list(group.interface.items_tree):
        group.interface.remove(sock)

    gin = nodes.new("NodeGroupInput")
    gout = nodes.new("NodeGroupOutput")
    gin.location = (-1200, 0)
    gout.location = (700, 0)

    settings = bpy.context.scene.blend_layer_settings
    layer_ids = str_to_list(settings.layer_list)
    layer_ids = sorted(list(set(layer_ids)))
    if len(layer_ids) < 1:
        layer_ids = [0]
        settings.layer_list = list_to_str(layer_ids)

    # ===== OUTPUT PORTS =====
    group.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    if settings.use_displacement:
        group.interface.new_socket("Displacement", in_out="OUTPUT", socket_type="NodeSocketVector")

    # ===== INPUT PORTS 严格顺序 =====
    group.interface.new_socket("Layer0_Shader", in_out="INPUT", socket_type="NodeSocketShader")
    if settings.use_displacement:
        group.interface.new_socket("Layer0_Displacement", in_out="INPUT", socket_type="NodeSocketColor")

    for lid in layer_ids[1:]:
        group.interface.new_socket(f"Layer{lid}_Shader", in_out="INPUT", socket_type="NodeSocketShader")
        if settings.use_displacement:
            group.interface.new_socket(f"Layer{lid}_Displacement", in_out="INPUT", socket_type="NodeSocketColor")
        mask_sock = group.interface.new_socket(f"Layer{lid}_Mask", in_out="INPUT", socket_type="NodeSocketFloat")
        mask_sock.default_value = 0.5
        mask_sock.min_value = 0.0
        mask_sock.max_value = 1.0

    shader_mix_list = []
    disp_mix_list = []
    y_step = -250

    for i in range(1, len(layer_ids)):
        mix_shader = nodes.new("ShaderNodeMixShader")
        mix_shader.location = (-300, y_step * i)
        shader_mix_list.append(mix_shader)

        if settings.use_displacement:
            mix_disp = nodes.new("ShaderNodeMix")
            mix_disp.data_type = "RGBA"
            mix_disp.blend_type = "MIX"
            mix_disp.location = (-300, y_step * i -120)
            disp_mix_list.append(mix_disp)

    # =========== Shader 混合链路 ===========
    layer0_shader = get_socket_by_name(gin, "Layer0_Shader")
    if len(layer_ids) == 1:
        out_shader = get_socket_by_name(gout, "Shader")
        if layer0_shader and out_shader:
            links.new(layer0_shader, out_shader)
    else:
        l1_shader = get_socket_by_name(gin, "Layer1_Shader")
        l1_mask = get_socket_by_name(gin, "Layer1_Mask")
        if layer0_shader and l1_shader and l1_mask:
            links.new(layer0_shader, shader_mix_list[0].inputs[1])
            links.new(l1_shader, shader_mix_list[0].inputs[2])
            links.new(l1_mask, shader_mix_list[0].inputs[0])

        for idx in range(1, len(shader_mix_list)):
            prev_mix = shader_mix_list[idx-1]
            curr_mix = shader_mix_list[idx]
            lid = layer_ids[idx+1]
            curr_shader = get_socket_by_name(gin, f"Layer{lid}_Shader")
            curr_mask = get_socket_by_name(gin, f"Layer{lid}_Mask")
            if curr_shader and curr_mask:
                links.new(prev_mix.outputs["Shader"], curr_mix.inputs[1])
                links.new(curr_shader, curr_mix.inputs[2])
                links.new(curr_mask, curr_mix.inputs[0])

        final_shader_out = get_socket_by_name(gout, "Shader")
        links.new(shader_mix_list[-1].outputs["Shader"], final_shader_out)

    # =========== Displacement RGBA颜色混合链路 ===========
    if settings.use_displacement:
        layer0_disp = get_socket_by_name(gin, "Layer0_Displacement")
        if len(layer_ids) == 1:
            out_disp = get_socket_by_name(gout, "Displacement")
            if layer0_disp and out_disp:
                links.new(layer0_disp, out_disp)
        else:
            l1_disp = get_socket_by_name(gin, "Layer1_Displacement")
            l1_mask = get_socket_by_name(gin, "Layer1_Mask")
            if layer0_disp and l1_disp and l1_mask:
                links.new(layer0_disp, disp_mix_list[0].inputs['A'])
                links.new(l1_disp, disp_mix_list[0].inputs['B'])
                links.new(l1_mask, disp_mix_list[0].inputs['Factor'])

            for idx in range(1, len(disp_mix_list)):
                prev_mix = disp_mix_list[idx-1]
                curr_mix = disp_mix_list[idx]
                lid = layer_ids[idx+1]
                curr_disp = get_socket_by_name(gin, f"Layer{lid}_Displacement")
                curr_mask = get_socket_by_name(gin, f"Layer{lid}_Mask")
                if curr_disp and curr_mask:
                    links.new(prev_mix.outputs['Result'], curr_mix.inputs['A'])
                    links.new(curr_disp, curr_mix.inputs['B'])
                    links.new(curr_mask, curr_mix.inputs['Factor'])

            final_disp_out = get_socket_by_name(gout, "Displacement")
            links.new(disp_mix_list[-1].outputs["Result"], final_disp_out)


class BLEND_OT_AddLayer(bpy.types.Operator):
    bl_idname = "blendlayers.add_layer"
    bl_label = "Add Layer"
    def execute(self, context):
        settings = context.scene.blend_layer_settings
        layers = str_to_list(settings.layer_list)
        new_id = max(layers) + 1
        layers.append(new_id)
        settings.layer_list = list_to_str(layers)
        settings.active_layer = new_id
        ng = get_group()
        rebuild_group(ng)
        self.report({"INFO"}, f"Added layer {new_id}")
        return {"FINISHED"}


class BLEND_OT_DeleteLayer(bpy.types.Operator):
    bl_idname = "blendlayers.delete_layer"
    bl_label = "Delete Active Layer"
    def execute(self, context):
        settings = context.scene.blend_layer_settings
        layers = str_to_list(settings.layer_list)
        active = settings.active_layer
        if len(layers) <= 1:
            self.report({"WARNING"}, "Must keep at least one layer")
            return {"CANCELLED"}
        if active in layers:
            layers.remove(active)
        settings.layer_list = list_to_str(layers)
        settings.active_layer = layers[-1]
        ng = get_group()
        rebuild_group(ng)
        self.report({"INFO"}, f"Deleted layer {active}")
        return {"FINISHED"}


class BLEND_OT_MoveUp(bpy.types.Operator):
    bl_idname = "blendlayers.move_up"
    bl_label = "Move Layer Up"
    def execute(self, context):
        settings = context.scene.blend_layer_settings
        layers = str_to_list(settings.layer_list)
        active = settings.active_layer
        idx = layers.index(active)
        if idx >= len(layers) - 1:
            self.report({"WARNING"}, "Already top layer")
            return {"CANCELLED"}
        layers[idx], layers[idx+1] = layers[idx+1], layers[idx]
        settings.layer_list = list_to_str(layers)
        ng = get_group()
        rebuild_group(ng)
        self.report({"INFO"}, f"Moved {active} up")
        return {"FINISHED"}


class BLEND_OT_MoveDown(bpy.types.Operator):
    bl_idname = "blendlayers.move_down"
    bl_label = "Move Layer Down"
    def execute(self, context):
        settings = context.scene.blend_layer_settings
        layers = str_to_list(settings.layer_list)
        active = settings.active_layer
        idx = layers.index(active)
        if idx <= 0:
            self.report({"WARNING"}, "Already bottom layer")
            return {"CANCELLED"}
        layers[idx], layers[idx-1] = layers[idx-1], layers[idx]
        settings.layer_list = list_to_str(layers)
        ng = get_group()
        rebuild_group(ng)
        self.report({"INFO"}, f"Moved {active} down")
        return {"FINISHED"}


class BLEND_OT_AddGroupToCurrentMat(bpy.types.Operator):
    bl_idname = "blendlayers.add_group_current_mat"
    bl_label = "Add Layer Group To Current Material"
    def execute(self, context):
        space = context.space_data
        if space.type != 'NODE_EDITOR' or space.tree_type != 'ShaderNodeTree':
            self.report({"ERROR"}, "Must be in Shader Editor")
            return {"CANCELLED"}
        mat = space.id
        if mat is None:
            self.report({"ERROR"}, "No active material in shader editor")
            return {"CANCELLED"}
        if not mat.use_nodes:
            mat.use_nodes = True

        node_tree = mat.node_tree
        nodes = node_tree.nodes
        ng = get_group()
        gn = nodes.new("ShaderNodeGroup")
        gn.node_tree = ng
        gn.location = space.cursor_location

        self.report({"INFO"}, "Layer group added to current shader canvas")
        return {"FINISHED"}


class BLEND_OT_SelectLayer(bpy.types.Operator):
    bl_idname = "blendlayers.select_layer"
    bl_label = "Select Layer"
    layer_id: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.blend_layer_settings.active_layer = self.layer_id
        return {"FINISHED"}


class BLEND_PT_Panel(bpy.types.Panel):
    bl_label = "Blend Material Layers"
    bl_idname = "BLEND_PT_Panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "BlendLayers"

    def draw(self, context):
        layout = self.layout
        try:
            settings = context.scene.blend_layer_settings
            layers = str_to_list(settings.layer_list)
            active = settings.active_layer

            # 1. 添加组按钮（顶部）
            layout.operator("blendlayers.add_group_current_mat", icon="NODETREE")
            layout.separator()

            # 新增：置换开关
            layout.prop(settings, "use_displacement")
            layout.separator()

            # 2. 图层控制按钮
            row = layout.row()
            row.operator("blendlayers.add_layer", icon="ADD")
            row.operator("blendlayers.delete_layer", icon="REMOVE")

            row = layout.row()
            row.operator("blendlayers.move_up", icon="TRIA_UP")
            row.operator("blendlayers.move_down", icon="TRIA_DOWN")

            layout.separator()

            # 3. 图层列表放到【最下方】
            box = layout.box()
            box.label(text="Layer list (0 = bottom layer)")
            for lid in layers:
                row = box.row()
                op = row.operator("blendlayers.select_layer",
                                  text=f"Layer {lid}",
                                  icon="CHECKMARK" if lid == active else "DOT")
                op.layer_id = lid

        except Exception as e:
            layout.label(text=f"UI Err: {str(e)}")


classes = [
    BlendLayerSettings,
    BLEND_OT_AddLayer,
    BLEND_OT_DeleteLayer,
    BLEND_OT_MoveUp,
    BLEND_OT_MoveDown,
    BLEND_OT_AddGroupToCurrentMat,
    BLEND_OT_SelectLayer,
    BLEND_PT_Panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blend_layer_settings = bpy.props.PointerProperty(type=BlendLayerSettings)


def unregister():
    del bpy.types.Scene.blend_layer_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
    print("✅ BlendLayers v2.3 loaded | Toggle displacement checkbox")
