extends Node
## DevConsole: the automation contract's entry point (design document, chapter 17).
##
## QA's bots and the team's tools call exec(command, args) and listen to the event
## signal. Every command answers {"ok": false, "error": "not implemented"} until the
## game's systems arrive; replace this script as they do.

@warning_ignore("unused_signal")
signal event(name: String, data: Dictionary)


func exec(_command: String, _args: Dictionary = {}) -> Dictionary:
	return {"ok": false, "error": "not implemented"}
