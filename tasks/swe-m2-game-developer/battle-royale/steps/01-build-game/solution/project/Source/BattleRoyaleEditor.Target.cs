using UnrealBuildTool;

public class BattleRoyaleEditorTarget : TargetRules
{
    public BattleRoyaleEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BattleRoyale");
    }
}
