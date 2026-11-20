using UnrealBuildTool;

public class BattleRoyaleTarget : TargetRules
{
    public BattleRoyaleTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BattleRoyale");
    }
}
