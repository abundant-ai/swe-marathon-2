#include "BRHUD.h"

#include "BRCharacter.h"
#include "BRController.h"
#include "BRMatch.h"
#include "BRTypes.h"
#include "BRVehicle.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

namespace
{
constexpr double ArenaHalfExtent = 10000.0;
constexpr float Margin = 32.0f;
constexpr float MaxHealth = 100.0f;
const FLinearColor Background(0.014f, 0.024f, 0.028f, 0.94f);
const FLinearColor Surface(0.033f, 0.066f, 0.071f, 0.95f);
const FLinearColor Divider(0.119f, 0.235f, 0.239f, 1.0f);
const FLinearColor Bright(0.90f, 0.96f, 0.94f, 1.0f);
const FLinearColor Muted(0.62f, 0.76f, 0.75f, 1.0f);
const FLinearColor Signal(0.31f, 0.89f, 0.70f, 1.0f);
const FLinearColor Warning(1.0f, 0.56f, 0.33f, 1.0f);

struct FBRHudPainter
{
    UCanvas& Canvas;
    UFont* Font;
    float Scale;
    float Width;
    float Height;

    explicit FBRHudPainter(UCanvas& InCanvas, UFont* InFont)
        : Canvas(InCanvas), Font(InFont),
          Scale(FMath::Min(InCanvas.ClipX / 1600.0f, InCanvas.ClipY / 900.0f)),
          Width(InCanvas.ClipX / Scale), Height(InCanvas.ClipY / Scale)
    {
    }

    void Fill(float X, float Y, float W, float H, const FLinearColor& Color) const
    {
        if (W <= 0.0f || H <= 0.0f)
        {
            return;
        }
        FCanvasTileItem Item(FVector2D(X, Y) * Scale, FVector2D(W, H) * Scale, Color);
        Item.BlendMode = SE_BLEND_Translucent;
        Canvas.DrawItem(Item);
    }

    void Line(FVector2D Start, FVector2D End, const FLinearColor& Color, float Thickness = 1.0f) const
    {
        FCanvasLineItem Item(Start * Scale, End * Scale);
        Item.SetColor(Color);
        Item.LineThickness = FMath::Max(1.0f, Thickness * Scale);
        Canvas.DrawItem(Item);
    }

    void Panel(float X, float Y, float W, float H) const
    {
        Fill(X, Y, W, H, Background);
        Fill(X, Y, W, 1.0f, Divider);
        Fill(X, Y + H - 1.0f, W, 1.0f, Divider);
        Fill(X, Y, 1.0f, H, Divider);
        Fill(X + W - 1.0f, Y, 1.0f, H, Divider);
    }

    // Align is the fraction of the measured string to place left of X.
    void Label(float X, float Y, const FString& Text, float Size = 1.0f,
               const FLinearColor& Color = Bright, float Align = 0.0f) const
    {
        if (Text.IsEmpty())
        {
            return;
        }
        if (Align != 0.0f)
        {
            float TextWidth = 0.0f;
            float TextHeight = 0.0f;
            Canvas.StrLen(Font, FStringView(*Text, Text.Len()), TextWidth, TextHeight, false);
            X -= TextWidth * Size * Align;
        }
        FCanvasTextItem Item(FVector2D(X, Y) * Scale, FText::FromString(Text), Font, Color);
        Item.Scale = FVector2D(Size * Scale);
        Item.EnableShadow(FLinearColor::Black, FVector2D(1.0, 1.0));
        Canvas.DrawItem(Item);
    }

    void Button(float X, float Y, float W, const FString& Key, const FString& Action, bool bAccent = false) const
    {
        Fill(X, Y, W, 43.0f, Surface);
        Fill(X, Y, 3.0f, 43.0f, bAccent ? Signal : Divider);
        Label(X + 13.0f, Y + 12.0f, Key, 0.95f, bAccent ? Signal : Muted);
        Label(X + W - 13.0f, Y + 10.0f, Action, 1.1f, Bright, 1.0f);
    }
};

FString TimeLabel(double Seconds)
{
    const int32 Total = FMath::CeilToInt(FMath::Clamp(Seconds, 0.0, 5999.0));
    return FString::Printf(TEXT("%02d:%02d"), Total / 60, Total % 60);
}

FString RifleLabel(EBRRifle Rifle)
{
    switch (Rifle)
    {
    case EBRRifle::AK47:
        return TEXT("AK-47");
    case EBRRifle::M16:
        return TEXT("M16");
    default:
        return TEXT("UNARMED");
    }
}

FString PlayerLabel(int32 Slot)
{
    return Slot == INDEX_NONE ? TEXT("Unassigned") : FString::Printf(TEXT("Player %d"), Slot + 1);
}

void DrawLobby(const FBRHudPainter& P, const ABRController& Controller, const ABRGameState* State)
{
    constexpr float W = 712.0f;
    constexpr float H = 416.0f;
    const float X = (P.Width - W) * 0.5f;
    const float Y = (P.Height - H) * 0.5f;
    const bool bReady = Controller.IsLocalReady();
    const bool bStandalone = Controller.GetNetMode() == NM_Standalone;
    const int32 Connected = State ? State->ConnectedCount : 0;
    const int32 Ready = State ? State->ReadyCount : 0;

    P.Fill(0.0f, 0.0f, P.Width, P.Height, FLinearColor(0.008f, 0.016f, 0.020f, 0.45f));
    P.Panel(X, Y, W, H);
    P.Fill(X, Y, W, 3.0f, Signal);
    P.Label(X + 32.0f, Y + 28.0f, TEXT("MATCH LOBBY"), 1.04f, Signal);
    P.Label(X + 30.0f, Y + 52.0f, TEXT("BASIN SIGNAL"), 3.15f);
    P.Label(X + 33.0f, Y + 122.0f, TEXT("Two-player battle royale"), 1.25f, Muted);

    P.Fill(X + 32.0f, Y + 166.0f, W - 64.0f, 1.0f, Divider);
    P.Label(X + 32.0f, Y + 191.0f, TEXT("CONNECTED"), 0.91f, Muted);
    P.Label(X + 32.0f, Y + 216.0f, FString::Printf(TEXT("%d / 2"), Connected), 1.53f);
    P.Label(X + 244.0f, Y + 191.0f, TEXT("READY"), 0.91f, Muted);
    P.Label(X + 244.0f, Y + 216.0f, FString::Printf(TEXT("%d / 2"), Ready), 1.53f);
    P.Label(X + 456.0f, Y + 191.0f, TEXT("YOU"), 0.91f, Muted);
    P.Label(X + 456.0f, Y + 216.0f, PlayerLabel(Controller.GetLocalSlot()), 1.53f);

    if (bStandalone)
    {
        P.Button(X + 32.0f, Y + 272.0f, 314.0f, TEXT("F1"), TEXT("Host"), true);
        P.Button(X + 366.0f, Y + 272.0f, 314.0f, TEXT("F2"), TEXT("Join"));
        P.Label(X + 32.0f, Y + 347.0f, TEXT("Host a lobby or join the configured address."), 1.075f, Muted);
    }
    else
    {
        P.Button(X + 32.0f, Y + 272.0f, W - 64.0f, TEXT("Enter"), bReady ? TEXT("Unready") : TEXT("Ready"), true);
        P.Label(X + 32.0f, Y + 347.0f,
                Connected < 2 ? TEXT("Waiting for a second player to connect.") :
                TEXT("The match starts when both players are ready."), 1.075f, Muted);
    }
}

void DrawResult(const FBRHudPainter& P, const ABRController& Controller, const ABRGameState& State)
{
    constexpr float W = 588.0f;
    constexpr float H = 292.0f;
    const float X = (P.Width - W) * 0.5f;
    const float Y = (P.Height - H) * 0.5f;
    const int32 Slot = Controller.GetLocalSlot();
    const FLinearColor OutcomeColor = !State.bDraw && Slot != INDEX_NONE && State.WinnerSlot != Slot ? Warning : Signal;
    const FString Outcome = State.bDraw ? TEXT("DRAW") :
        (Slot == INDEX_NONE ? TEXT("MATCH COMPLETE") : (State.WinnerSlot == Slot ? TEXT("VICTORY") : TEXT("ELIMINATED")));
    const FString Detail = State.bDraw ? TEXT("Both players were eliminated.") :
        FString::Printf(TEXT("%s wins the match."), *PlayerLabel(State.WinnerSlot));

    P.Fill(0.0f, 0.0f, P.Width, P.Height, FLinearColor(0.008f, 0.016f, 0.020f, 0.45f));
    P.Panel(X, Y, W, H);
    P.Fill(X, Y, W, 3.0f, OutcomeColor);
    P.Label(X + 28.0f, Y + 29.0f, FString::Printf(TEXT("MATCH %d  /  RESULT"), State.MatchSerial), 0.97f, Signal);
    P.Label(X + 26.0f, Y + 57.0f, Outcome, 2.75f, OutcomeColor);
    P.Label(X + 28.0f, Y + 126.0f, Detail, 1.1f, Muted);
    P.Button(X + 28.0f, Y + 174.0f, W - 56.0f, TEXT("Enter"),
             Controller.IsLocalReady() ? TEXT("Unready") : TEXT("Ready for rematch"), true);
    P.Label(X + 28.0f, Y + 237.0f, FString::Printf(TEXT("%d / 2 ready for the next match"), State.ReadyCount), 1.02f, Muted);
}

void DrawMap(const FBRHudPainter& P, const ABRCharacter& Character, const ABRGameState& State)
{
    constexpr float W = 232.0f;
    constexpr float H = 258.0f;
    constexpr float PlotSize = 200.0f;
    const float X = P.Width - Margin - W;
    constexpr float Y = Margin;
    const float PlotX = X + 16.0f;
    constexpr float PlotY = Y + 42.0f;
    const auto Project = [&](const FVector& Position)
    {
        const double U = (Position.X + ArenaHalfExtent) / (2.0 * ArenaHalfExtent);
        const double V = (ArenaHalfExtent - Position.Y) / (2.0 * ArenaHalfExtent);
        return FVector2D(PlotX + PlotSize * U, PlotY + PlotSize * V);
    };
    const auto InPlot = [&](const FVector2D& Point)
    {
        return Point.X >= PlotX && Point.X <= PlotX + PlotSize && Point.Y >= PlotY && Point.Y <= PlotY + PlotSize;
    };

    P.Panel(X, Y, W, H);
    P.Label(PlotX, Y + 13.0f, TEXT("TACTICAL MAP"), 0.94f, Muted);
    P.Label(X + W - 16.0f, Y + 13.0f, TEXT("N"), 1.0f, Bright, 1.0f);
    P.Fill(PlotX, PlotY, PlotSize, PlotSize, Surface);
    for (int32 Line = 1; Line < 4; ++Line)
    {
        const float Offset = Line * (PlotSize * 0.25f);
        P.Line(FVector2D(PlotX + Offset, PlotY), FVector2D(PlotX + Offset, PlotY + PlotSize), Divider);
        P.Line(FVector2D(PlotX, PlotY + Offset), FVector2D(PlotX + PlotSize, PlotY + Offset), Divider);
    }

    const FVector2D Center = Project(State.ZoneCenter);
    const double Radius = PlotSize * State.ZoneRadius / (2.0 * ArenaHalfExtent);
    if (Radius > 0.0)
    {
        constexpr int32 Segments = 48;
        FVector2D Previous = Center + FVector2D(Radius, 0.0);
        for (int32 Index = 1; Index <= Segments; ++Index)
        {
            const double Theta = Index * (2.0 * UE_DOUBLE_PI / Segments);
            const FVector2D Next = Center + FVector2D(FMath::Cos(Theta), FMath::Sin(Theta)) * Radius;
            if (InPlot(Previous) && InPlot(Next))
            {
                P.Line(Previous, Next, Signal, 2.0f);
            }
            Previous = Next;
        }
    }

    // Project only the locally controlled player's position.
    const FVector2D Position = Project(Character.GetActorLocation());
    const float OwnX = FMath::Clamp(static_cast<float>(Position.X), PlotX + 4.0f, PlotX + PlotSize - 4.0f);
    const float OwnY = FMath::Clamp(static_cast<float>(Position.Y), PlotY + 4.0f, PlotY + PlotSize - 4.0f);
    P.Fill(OwnX - 4.0f, OwnY - 4.0f, 8.0f, 8.0f, Background);
    P.Fill(OwnX - 2.0f, OwnY - 2.0f, 4.0f, 4.0f, Bright);
}

void DrawInventory(const FBRHudPainter& P, const ABRCharacter& Character)
{
    constexpr float X = Margin;
    constexpr float W = 363.0f;
    constexpr float H = 219.0f;
    const float Y = (P.Height - H) * 0.5f;
    P.Panel(X, Y, W, H);
    P.Fill(X, Y, 3.0f, H, Signal);
    P.Label(X + 17.0f, Y + 15.0f, TEXT("INVENTORY"), 1.15f);
    P.Label(X + W - 15.0f, Y + 17.0f, TEXT("Tab  Close"), 0.95f, Muted, 1.0f);
    P.Label(X + 234.0f, Y + 55.0f, TEXT("LOADED"), 0.80f, Muted, 1.0f);
    P.Label(X + 347.0f, Y + 55.0f, TEXT("RESERVE"), 0.80f, Muted, 1.0f);
    constexpr EBRRifle Rifles[] = {EBRRifle::AK47, EBRRifle::M16};
    int32 Index = 0;
    for (const EBRRifle Rifle : Rifles)
    {
        const float Row = Y + 77.0f + Index * 61.0f;
        const bool bOwned = Character.OwnsRifle(Rifle);
        const bool bEquipped = Rifle == Character.GetEquippedRifle();
        P.Fill(X + 15.0f, Row, W - 30.0f, 49.0f, Surface);
        P.Label(X + 26.0f, Row + 12.0f, FString::Printf(TEXT("%d"), Index + 1), 0.95f, Signal);
        P.Label(X + 56.0f, Row + 10.0f, RifleLabel(Rifle), 1.12f, bEquipped ? Signal : Bright);
        P.Label(X + 56.0f, Row + 28.0f, bOwned ? (bEquipped ? TEXT("Equipped") : TEXT("Carried")) : TEXT("Empty slot"), 0.80f, Muted);
        P.Label(X + 223.0f, Row + 13.0f, FString::FromInt(Character.GetLoadedAmmo(Rifle)), 1.1f, Bright, 1.0f);
        P.Label(X + 335.0f, Row + 13.0f, FString::FromInt(Character.GetReserveAmmo(Rifle)), 1.1f, Bright, 1.0f);
        ++Index;
    }
}

void DrawVitalsAndEquipment(const FBRHudPainter& P, const ABRCharacter& Character, double ServerTime)
{
    constexpr float VitalsWidth = 248.0f;
    constexpr float EquipmentWidth = 261.0f;
    constexpr float H = 106.0f;
    const float Y = P.Height - Margin - H;
    const float EquipmentX = P.Width - Margin - EquipmentWidth;
    const float Health = FMath::Clamp(static_cast<float>(Character.GetHealth()), 0.0f, MaxHealth);
    const FLinearColor HealthColor = Health <= 25.0f ? Warning : Signal;

    P.Panel(Margin, Y, VitalsWidth, H);
    P.Label(Margin + 16.0f, Y + 13.0f, TEXT("HEALTH"), 0.97f, Muted);
    P.Label(Margin + 16.0f, Y + 34.0f, FString::FromInt(FMath::CeilToInt(Health)), 1.75f, HealthColor);
    P.Label(Margin + VitalsWidth - 16.0f, Y + 48.0f, TEXT("/ 100"), 0.95f, Muted, 1.0f);
    P.Fill(Margin + 16.0f, Y + 77.0f, VitalsWidth - 32.0f, 8.0f, Divider);
    P.Fill(Margin + 16.0f, Y + 77.0f, (VitalsWidth - 32.0f) * (Health / MaxHealth), 8.0f, HealthColor);

    P.Panel(EquipmentX, Y, EquipmentWidth, H);
    const EBRRifle Rifle = Character.GetEquippedRifle();
    const ABRVehicle* Vehicle = Character.GetVehicle();
    if (Vehicle)
    {
        const int32 Speed = FMath::RoundToInt(FMath::Abs(Vehicle->GetForwardSpeed()) * 0.036f);
        P.Label(EquipmentX + 16.0f, Y + 13.0f, TEXT("VEHICLE"), 0.97f, Muted);
        P.Label(EquipmentX + 16.0f, Y + 36.0f, FString::Printf(TEXT("%d km/h"), Speed), 1.75f);
        P.Label(EquipmentX + 16.0f, Y + 79.0f, TEXT("E  Exit vehicle"), 0.95f, Signal);
    }
    else
    {
        P.Label(EquipmentX + 16.0f, Y + 13.0f, RifleLabel(Rifle), 0.97f, Muted);
        if (Rifle == EBRRifle::None)
        {
            P.Label(EquipmentX + 16.0f, Y + 43.0f, TEXT("E  Collect loot"), 1.25f);
        }
        else
        {
            const int32 Loaded = Character.GetLoadedAmmo(Rifle);
            const int32 Reserve = Character.GetReserveAmmo(Rifle);
            P.Label(EquipmentX + 16.0f, Y + 32.0f, FString::Printf(TEXT("%02d"), Loaded), 1.88f, Loaded > 0 ? Bright : Warning);
            P.Label(EquipmentX + EquipmentWidth - 16.0f, Y + 41.0f,
                    FString::Printf(TEXT("/ %d reserve"), Reserve), 1.05f, Muted, 1.0f);
            const FString Reload = Character.IsReloading() ?
                FString::Printf(TEXT("Reloading  %.1fs"), FMath::Max(0.0, Character.GetReloadEndTime() - ServerTime)) :
                TEXT("R  Reload   /   Tab  Inventory");
            P.Label(EquipmentX + 16.0f, Y + 79.0f, Reload, 0.95f, Signal);
        }
    }
}

void DrawPlaying(const FBRHudPainter& P, const ABRController& Controller,
                 const ABRCharacter& Character, const ABRGameState& State)
{
    constexpr float ZoneWidth = 281.0f;
    const float CenterX = P.Width * 0.5f;
    const float CenterY = P.Height * 0.5f;
    const double ServerTime = State.GetServerWorldTimeSeconds();
    const FVector ToZone = Character.GetActorLocation() - State.ZoneCenter;
    const bool bOutside = FVector2D(ToZone.X, ToZone.Y).SizeSquared() > FMath::Square(static_cast<double>(State.ZoneRadius));
    const bool bDriving = Character.GetVehicle() != nullptr;
    const bool bEliminated = Character.IsEliminated();
    const bool bInventory = Controller.IsInventoryOpen();

    P.Label(Margin, Margin, FString::Printf(TEXT("MATCH %d"), State.MatchSerial), 1.03f);
    P.Label(Margin, Margin + 25.0f, PlayerLabel(Controller.GetLocalSlot()), 0.97f, Muted);
    P.Panel(CenterX - ZoneWidth * 0.5f, Margin, ZoneWidth, 71.0f);
    P.Label(CenterX, Margin + 9.0f, bOutside ? TEXT("OUTSIDE SAFE ZONE") : TEXT("NEXT ZONE CHANGE"),
            0.95f, bOutside ? Warning : Signal, 0.5f);
    const FString Countdown = State.NextZoneChangeTime > 0.0 ?
        TimeLabel(State.NextZoneChangeTime - ServerTime) : TEXT("FINAL ZONE");
    P.Label(CenterX, Margin + 28.0f, Countdown, 1.65f, Bright, 0.5f);
    DrawMap(P, Character, State);
    DrawVitalsAndEquipment(P, Character, ServerTime);

    if (bEliminated)
    {
        P.Panel(CenterX - 198.0f, CenterY - 54.0f, 396.0f, 92.0f);
        P.Label(CenterX, CenterY - 43.0f, TEXT("ELIMINATED"), 1.55f, Warning, 0.5f);
        P.Label(CenterX, CenterY - 2.0f, TEXT("Waiting for the match result"), 1.02f, Muted, 0.5f);
        return;
    }
    if (bInventory)
    {
        DrawInventory(P, Character);
    }
    if (!bInventory && !bDriving)
    {
        const float Gap = Character.IsAiming() ? 4.0f : 6.0f;
        const float Reach = Gap + 6.0f;
        P.Line(FVector2D(CenterX - Reach, CenterY), FVector2D(CenterX - Gap, CenterY), Bright);
        P.Line(FVector2D(CenterX + Gap, CenterY), FVector2D(CenterX + Reach, CenterY), Bright);
        P.Line(FVector2D(CenterX, CenterY - Reach), FVector2D(CenterX, CenterY - Gap), Bright);
        P.Line(FVector2D(CenterX, CenterY + Gap), FVector2D(CenterX, CenterY + Reach), Bright);
    }

    const FString Feedback = Character.GetActionFeedback();
    P.Label(CenterX, CenterY + 39.0f, Feedback, 1.09f, Signal, 0.5f);
    constexpr float ControlsWidth = 654.0f;
    const float ControlsY = P.Height - Margin - 51.0f;
    P.Panel(CenterX - ControlsWidth * 0.5f, ControlsY, ControlsWidth, 51.0f);
    P.Label(CenterX, ControlsY + 15.0f,
            bDriving ? TEXT("W/S  Drive   A/D  Steer   Space  Brake   E  Exit") :
            TEXT("WASD  Move   Shift  Sprint   Space  Jump   E  Interact   RMB  Aim   LMB  Fire   1/2  Equip"),
            0.92f, Muted, 0.5f);
}
}

void ABRHUD::DrawHUD()
{
    Super::DrawHUD();
    const ABRController* Controller = Cast<ABRController>(GetOwningPlayerController());
    UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
    UWorld* World = GetWorld();
    if (!Controller || !Canvas || !Font || !World || Canvas->ClipX <= 0.0f || Canvas->ClipY <= 0.0f)
    {
        return;
    }
    const ABRGameState* State = Cast<ABRGameState>(World->GetGameState());
    const FBRHudPainter Painter(*Canvas, Font);
    if (!State || State->Phase == EBRMatchPhase::Waiting)
    {
        DrawLobby(Painter, *Controller, State);
    }
    else if (State->Phase == EBRMatchPhase::Finished)
    {
        DrawResult(Painter, *Controller, *State);
    }
    else if (const ABRCharacter* Character = Cast<ABRCharacter>(Controller->GetPawn()))
    {
        DrawPlaying(Painter, *Controller, *Character, *State);
    }
}
