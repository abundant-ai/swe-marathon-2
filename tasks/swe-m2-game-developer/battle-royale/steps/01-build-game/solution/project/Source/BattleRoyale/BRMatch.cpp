#include "BRMatch.h"

#include "BRCharacter.h"
#include "BRController.h"
#include "BRHUD.h"
#include "BRLoot.h"
#include "BRVehicle.h"
#include "BRWorld.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameSession.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
constexpr float InitialRadius = 8000.0f;
constexpr float PerimeterDamage = 9.0f;

struct FZoneLeg
{
    double HoldSeconds;
    double CloseSeconds;
    float TargetRadius;
};

constexpr FZoneLeg ZoneSchedule[] = {
    {35, 24, 5900},
    {28, 22, 3800},
    {23, 20, 1900},
    {15, 18, 500},
    {12, 15, 0}
};

void UpdatePerimeter(ABRGameState& Match, double StartTime, double Now)
{
    double Offset = 0.0;
    float FromRadius = InitialRadius;
    for (const FZoneLeg& Leg : ZoneSchedule)
    {
        const double HoldEnd = StartTime + Offset + Leg.HoldSeconds;
        const double CloseEnd = HoldEnd + Leg.CloseSeconds;
        if (Now < HoldEnd)
        {
            Match.SetZone(FromRadius, HoldEnd);
            return;
        }
        if (Now < CloseEnd)
        {
            const float Progress = static_cast<float>((Now - HoldEnd) / Leg.CloseSeconds);
            Match.SetZone(FMath::Lerp(FromRadius, Leg.TargetRadius, Progress), CloseEnd);
            return;
        }
        Offset += Leg.HoldSeconds + Leg.CloseSeconds;
        FromRadius = Leg.TargetRadius;
    }
    Match.SetZone(0.0f, 0.0);
}
}

ABRGameState::ABRGameState()
{
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Origin"));
    Boundary = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Perimeter"));
    Boundary->SetupAttachment(RootComponent);
    Boundary->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Boundary->SetCastShadow(false);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded())
    {
        Boundary->SetStaticMesh(Cube.Object);
    }
}

void ABRGameState::BeginPlay()
{
    Super::BeginPlay();
    BRWorld::BuildScenery(*GetWorld());
    OnRep_Zone();
}

void ABRGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABRGameState, Phase);
    DOREPLIFETIME(ABRGameState, ZoneCenter);
    DOREPLIFETIME(ABRGameState, ZoneRadius);
    DOREPLIFETIME(ABRGameState, NextZoneChangeTime);
    DOREPLIFETIME(ABRGameState, ConnectedCount);
    DOREPLIFETIME(ABRGameState, ReadyCount);
    DOREPLIFETIME(ABRGameState, WinnerSlot);
    DOREPLIFETIME(ABRGameState, bDraw);
    DOREPLIFETIME(ABRGameState, MatchSerial);
}

void ABRGameState::SetZone(float Radius, double NextChangeTime)
{
    NextZoneChangeTime = NextChangeTime;
    if (!FMath::IsNearlyEqual(ZoneRadius, Radius))
    {
        ZoneRadius = Radius;
        OnRep_Zone();
    }
}

void ABRGameState::OnRep_Zone()
{
    Boundary->ClearInstances();
    if (ZoneRadius < 10.0f || GetNetMode() == NM_DedicatedServer)
    {
        return;
    }
    constexpr int32 SegmentCount = 48;
    for (int32 Index = 0; Index < SegmentCount; ++Index)
    {
        const float StartAngle = 2.0f * UE_PI * Index / SegmentCount;
        const float EndAngle = 2.0f * UE_PI * (Index + 1) / SegmentCount;
        const FVector Start = ZoneCenter + FVector(FMath::Cos(StartAngle), FMath::Sin(StartAngle), 0) * ZoneRadius;
        const FVector End = ZoneCenter + FVector(FMath::Cos(EndAngle), FMath::Sin(EndAngle), 0) * ZoneRadius;
        const FVector Direction = End - Start;
        const FVector Midpoint = (Start + End) * 0.5 + FVector(0, 0, 135);
        Boundary->AddInstance(FTransform(Direction.Rotation(), Midpoint,
            FVector(Direction.Size() / 100.0, 0.08, 0.04)), true);
        Boundary->AddInstance(FTransform(FRotator::ZeroRotator, Start + FVector(0, 0, 90),
            FVector(0.12, 0.12, 1.8)), true);
    }
}

ABRGameMode::ABRGameMode()
{
    GameStateClass = ABRGameState::StaticClass();
    PlayerControllerClass = ABRController::StaticClass();
    DefaultPawnClass = ABRCharacter::StaticClass();
    HUDClass = ABRHUD::StaticClass();
}

ABRGameState* ABRGameMode::GetMatch() const
{
    return GetWorld()->GetGameState<ABRGameState>();
}

void ABRGameMode::StartPlay()
{
    Super::StartPlay();
    RefreshLobby();
    GetWorldTimerManager().SetTimer(RoundTimer, this, &ABRGameMode::TickRound, 0.25f, true);
    if (GetNetMode() == NM_ListenServer)
    {
        UE_LOG(LogTemp, Display, TEXT("BASIN listen session ready"));
    }
}

void ABRGameMode::PreLogin(const FString& Options, const FString& Address,
    const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
    Super::PreLogin(Options, Address, UniqueId, ErrorMessage);
    if (!ErrorMessage.IsEmpty())
    {
        return;
    }
    const ABRGameState* Match = GetMatch();
    if (Players[0].IsValid() && Players[1].IsValid())
    {
        ErrorMessage = TEXT("The two-player session is full.");
    }
    else if (Match && Match->IsPlaying())
    {
        ErrorMessage = TEXT("A round is in progress.");
    }
}

void ABRGameMode::PostLogin(APlayerController* NewPlayer)
{
    ABRController* Controller = Cast<ABRController>(NewPlayer);
    if (Controller)
    {
        for (int32 Slot = 0; Slot < 2; ++Slot)
        {
            if (!Players[Slot].IsValid())
            {
                Players[Slot] = Controller;
                Controller->SetSlot(Slot);
                break;
            }
        }
    }

    Super::PostLogin(NewPlayer);
    if (!Controller)
    {
        return;
    }
    if (Controller->GetLocalSlot() == INDEX_NONE)
    {
        if (GameSession)
        {
            GameSession->KickPlayer(Controller, FText::FromString(TEXT("The two-player session is full.")));
        }
        return;
    }
    if (!Controller->GetPawn())
    {
        RestartPlayer(Controller);
    }
    RefreshLobby();
    if (!Controller->IsLocalController())
    {
        UE_LOG(LogTemp, Display, TEXT("BASIN remote player admitted slot %d"), Controller->GetLocalSlot() + 1);
    }
}

void ABRGameMode::Logout(AController* Exiting)
{
    if (ABRCharacter* Pawn = Cast<ABRCharacter>(Exiting->GetPawn()))
    {
        if (ABRVehicle* Vehicle = Pawn->GetVehicle())
        {
            Vehicle->TryExit(Pawn, true);
        }
    }
    for (TWeakObjectPtr<ABRController>& Player : Players)
    {
        if (Player.Get() == Exiting)
        {
            Player.Reset();
        }
    }
    Super::Logout(Exiting);
    RefreshLobby();
    NotifyElimination(nullptr);
}

void ABRGameMode::RestartPlayer(AController* NewPlayer)
{
    const ABRController* Controller = Cast<ABRController>(NewPlayer);
    if (Controller && Controller->GetLocalSlot() != INDEX_NONE)
    {
        RestartPlayerAtTransform(NewPlayer, BRWorld::PlayerSpawn(Controller->GetLocalSlot()));
    }
}

void ABRGameMode::ToggleReady(ABRController& Controller)
{
    ABRGameState* Match = GetMatch();
    if (!Match || Match->IsPlaying())
    {
        return;
    }
    const int32 Slot = Controller.GetLocalSlot();
    if (Slot < 0 || Slot >= 2 || Players[Slot].Get() != &Controller)
    {
        return;
    }

    Controller.SetReady(!Controller.IsLocalReady());
    RefreshLobby();
    if (Match->ReadyCount == 2)
    {
        StartRound();
    }
}

void ABRGameMode::RefreshLobby()
{
    if (ABRGameState* Match = GetMatch())
    {
        Match->ConnectedCount = 0;
        Match->ReadyCount = 0;
        for (const TWeakObjectPtr<ABRController>& Player : Players)
        {
            if (const ABRController* Controller = Player.Get())
            {
                ++Match->ConnectedCount;
                Match->ReadyCount += Controller->IsLocalReady() ? 1 : 0;
            }
        }
        Match->ForceNetUpdate();
    }
}

void ABRGameMode::StartRound()
{
    ABRGameState& Match = *GetMatch();
    for (int32 Slot = 0; Slot < 2; ++Slot)
    {
        ABRController* Controller = Players[Slot].Get();
        if (!Controller)
        {
            return;
        }
        if (ABRCharacter* Pawn = Cast<ABRCharacter>(Controller->GetPawn()))
        {
            if (ABRVehicle* Vehicle = Pawn->GetVehicle())
            {
                Vehicle->TryExit(Pawn, true);
            }
            Pawn->ResetForMatch();
            const FTransform Spawn = BRWorld::PlayerSpawn(Slot);
            Pawn->SetActorLocationAndRotation(Spawn.GetLocation(), Spawn.Rotator(), false, nullptr, ETeleportType::TeleportPhysics);
            Controller->ClientSetRotation(Spawn.Rotator(), true);
        }
        else
        {
            RestartPlayer(Controller);
        }
        Controller->SetReady(false);
    }

    for (TActorIterator<ABRLoot> Item(GetWorld()); Item; ++Item)
    {
        Item->Destroy();
    }
    for (TActorIterator<ABRVehicle> Vehicle(GetWorld()); Vehicle; ++Vehicle)
    {
        Vehicle->Destroy();
    }
    BRWorld::SpawnInteractives(*GetWorld());

    RoundStartTime = Match.GetServerWorldTimeSeconds();
    NextDamageTime = RoundStartTime + 1.0;
    Match.WinnerSlot = INDEX_NONE;
    Match.bDraw = false;
    ++Match.MatchSerial;
    Match.Phase = EBRMatchPhase::Playing;
    UpdatePerimeter(Match, RoundStartTime, RoundStartTime);
    RefreshLobby();
    UE_LOG(LogTemp, Display, TEXT("BASIN match %d started with two players"), Match.MatchSerial);
}

void ABRGameMode::TickRound()
{
    ABRGameState* Match = GetMatch();
    if (!Match || !Match->IsPlaying())
    {
        return;
    }

    const double Now = Match->GetServerWorldTimeSeconds();
    UpdatePerimeter(*Match, RoundStartTime, Now);
    if (Now >= NextDamageTime)
    {
        NextDamageTime = Now + 1.0;
        for (const TWeakObjectPtr<ABRController>& Player : Players)
        {
            ABRController* Controller = Player.Get();
            ABRCharacter* Pawn = Controller ? Cast<ABRCharacter>(Controller->GetPawn()) : nullptr;
            if (Pawn && !Pawn->IsEliminated()
                && (Match->ZoneRadius <= 0.0f
                    || FVector::Dist2D(Pawn->GetActorLocation(), Match->ZoneCenter) > Match->ZoneRadius))
            {
                Pawn->ApplyAuthorityDamage(PerimeterDamage);
            }
        }
    }
}

void ABRGameMode::NotifyElimination(ABRCharacter* Player)
{
    const ABRGameState* Match = GetMatch();
    if (!bOutcomeQueued && Match && Match->IsPlaying())
    {
        bOutcomeQueued = true;
        GetWorldTimerManager().SetTimerForNextTick(this, &ABRGameMode::ResolveOutcome);
        if (Player)
        {
            UE_LOG(LogTemp, Display, TEXT("BASIN player eliminated in match %d"), Match->MatchSerial);
        }
    }
}

void ABRGameMode::ResolveOutcome()
{
    bOutcomeQueued = false;
    const ABRGameState* Match = GetMatch();
    if (!Match || !Match->IsPlaying())
    {
        return;
    }
    int32 Alive = 0;
    int32 LastAlive = INDEX_NONE;
    for (int32 Slot = 0; Slot < 2; ++Slot)
    {
        const ABRController* Controller = Players[Slot].Get();
        const ABRCharacter* Pawn = Controller ? Cast<ABRCharacter>(Controller->GetPawn()) : nullptr;
        if (Pawn && !Pawn->IsEliminated())
        {
            ++Alive;
            LastAlive = Slot;
        }
    }
    if (Alive < 2)
    {
        FinishRound(LastAlive, Alive == 0);
    }
}

void ABRGameMode::FinishRound(int32 Winner, bool bDrawResult)
{
    ABRGameState& Match = *GetMatch();
    Match.Phase = EBRMatchPhase::Finished;
    Match.WinnerSlot = Winner;
    Match.bDraw = bDrawResult;
    Match.SetZone(Match.ZoneRadius, 0.0);
    Match.ForceNetUpdate();
    UE_LOG(LogTemp, Display, TEXT("BASIN match %d finished winner=%d draw=%d"),
        Match.MatchSerial, Winner, bDrawResult ? 1 : 0);
}
