extends Node3D
## Main scene: hands over to the Game autoload, which builds the world from the plan.

func _ready() -> void:
	Game.boot(self)
