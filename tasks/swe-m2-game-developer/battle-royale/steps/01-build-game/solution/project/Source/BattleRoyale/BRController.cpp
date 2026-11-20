#include "BRController.h"

#include "BRCharacter.h"
#include "BRMatch.h"
#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Net/UnrealNetwork.h"

void ABRController::BeginPlay()
{
    Super::BeginPlay();
    bAutoReady = FParse::Param(FCommandLine::Get(), TEXT("BRAutoReady"));
}

void ABRController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (!bAutoReady || !IsLocalController() || Slot == INDEX_NONE)
    {
        return;
    }
    const ABRGameState* Match = GetWorld()->GetGameState<ABRGameState>();
    const ABRCharacter* Character = Cast<ABRCharacter>(GetPawn());
    if (!Match || !Character)
    {
        return;
    }

    const double Now = Match->GetServerWorldTimeSeconds();
    if (LastObservedSerial != Match->MatchSerial || LastObservedPhase != Match->Phase)
    {
        LastObservedSerial = Match->MatchSerial;
        LastObservedPhase = Match->Phase;
        PhaseObservedAt = Now;
        if (Match->IsPlaying())
        {
            UE_LOG(LogTemp, Display, TEXT("BASIN observed match %d playing as player %d"),
                Match->MatchSerial, Slot + 1);
        }
        else if (Match->Phase == EBRMatchPhase::Finished)
        {
            UE_LOG(LogTemp, Display, TEXT("BASIN observed match %d finished player=%d winner=%d draw=%d"),
                Match->MatchSerial, Slot + 1, Match->WinnerSlot, Match->bDraw ? 1 : 0);
        }
    }
    if (!Match->IsPlaying() && Match->ConnectedCount == 2 && LastReadySerial != Match->MatchSerial
        && Now - PhaseObservedAt >= 1.0)
    {
        LastReadySerial = Match->MatchSerial;
        if (!bReady)
        {
            ServerToggleReady();
        }
    }
    if (Match->IsPlaying() && LastFreshSerial != Match->MatchSerial
        && Character->GetHealth() >= 100.0f && Match->ZoneRadius >= 7999.0f)
    {
        LastFreshSerial = Match->MatchSerial;
        UE_LOG(LogTemp, Display, TEXT("BASIN observed match %d fresh as player %d"),
            Match->MatchSerial, Slot + 1);
    }
}

void ABRController::SetupInputComponent()
{
    Super::SetupInputComponent();
    InputComponent->BindAction("HostMatch", IE_Pressed, this, &ABRController::HostMatch);
    InputComponent->BindAction("JoinMatch", IE_Pressed, this, &ABRController::JoinMatch);
    InputComponent->BindAction("MatchReady", IE_Pressed, this, &ABRController::ToggleReady);
    InputComponent->BindAction("Inventory", IE_Pressed, this, &ABRController::ToggleInventory);
}

void ABRController::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABRController, Slot);
    DOREPLIFETIME(ABRController, bReady);
}

void ABRController::SetSlot(int32 NewSlot)
{
    Slot = NewSlot;
    ForceNetUpdate();
    OnRep_Slot();
}

void ABRController::SetReady(bool bNewReady)
{
    bReady = bNewReady;
    ForceNetUpdate();
}

void ABRController::OnRep_Slot()
{
    if (IsLocalController() && Slot != INDEX_NONE)
    {
        UE_LOG(LogTemp, Display, TEXT("BASIN session assigned player %d"), Slot + 1);
    }
}

void ABRController::HostMatch()
{
    if (GetNetMode() == NM_Standalone)
    {
        UGameplayStatics::OpenLevel(this, FName(TEXT("/Engine/Maps/Entry")), true, TEXT("listen"));
    }
}

void ABRController::JoinMatch()
{
    if (GetNetMode() != NM_Standalone)
    {
        return;
    }

    FString Address = TEXT("127.0.0.1:7777");
    FParse::Value(FCommandLine::Get(), TEXT("BRAddress="), Address);
    if (!Address.IsEmpty())
    {
        ClientTravel(Address, TRAVEL_Absolute);
    }
}

void ABRController::ToggleReady()
{
    ServerToggleReady();
}

void ABRController::ServerToggleReady_Implementation()
{
    if (ABRGameMode* Match = GetWorld()->GetAuthGameMode<ABRGameMode>())
    {
        Match->ToggleReady(*this);
    }
}

void ABRController::ToggleInventory()
{
    bShowInventory = !bShowInventory;
}
