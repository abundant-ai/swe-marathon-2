class_name Hud
extends RefCounted
## Minimal HUD: wanted level as five badges (group hud_wanted, one visible child per level).

static func build() -> CanvasLayer:
	var layer := CanvasLayer.new()
	layer.name = "HUD"
	var box := HBoxContainer.new()
	box.name = "Wanted"
	box.add_to_group("hud_wanted")
	box.position = Vector2(780, 16)
	for i in range(5):
		var b := Label.new()
		b.name = "Badge%d" % (i + 1)
		b.text = "[#]"
		b.visible = false
		box.add_child(b)
	layer.add_child(box)
	return layer


static func set_wanted(layer: CanvasLayer, level: int) -> void:
	var box := layer.get_node("Wanted")
	for i in range(box.get_child_count()):
		box.get_child(i).visible = i < level
