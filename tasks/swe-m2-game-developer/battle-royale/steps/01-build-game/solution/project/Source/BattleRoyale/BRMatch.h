#pragma once

#include "CoreMinimal.h"
#include "BRTypes.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/GameStateBase.h"
#include "TimerManager.h"
#include "BRMatch.generated.h"

class ABRCharacter;
class ABRController;
class UInstancedStaticMeshComponent;

UCLASS()
class BATTLEROYALE_API ABRGameState : public AGameStateBase
{
    GENERATED_BODY()

public:
    ABRGameState();

    UPROPERTY(Replicated)
    EBRMatchPhase Phase = EBRMatchPhase::Waiting;

    UPROPERTY(Replicated)
    FVector ZoneCenter = FVector::ZeroVector;

    UPROPERTY(ReplicatedUsing=OnRep_Zone)
    float ZoneRadius = 8000.0f;

    UPROPERTY(Replicated)
    double NextZoneChangeTime = 0.0;

    UPROPERTY(Replicated)
    int32 ConnectedCount = 0;

    UPROPERTY(Replicated)
    int32 ReadyCount = 0;

    UPROPERTY(Replicated)
    int32 WinnerSlot = INDEX_NONE;

    UPROPERTY(Replicated)
    bool bDraw = false;

    UPROPERTY(Replicated)
    int32 MatchSerial = 0;

    bool IsPlaying() const { return Phase == EBRMatchPhase::Playing; }
    void SetZone(float Radius, double NextChangeTime);

    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY()
    TObjectPtr<UInstancedStaticMeshComponent> Boundary;

    UFUNCTION()
    void OnRep_Zone();
};

UCLASS()
class BATTLEROYALE_API ABRGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    ABRGameMode();
    virtual void StartPlay() override;
    virtual void PreLogin(const FString& Options, const FString& Address,
        const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual void PostLogin(APlayerController* NewPlayer) override;
    virtual void Logout(AController* Exiting) override;
    virtual void RestartPlayer(AController* NewPlayer) override;

    void ToggleReady(ABRController& Controller);
    void NotifyElimination(ABRCharacter* Player);

private:
    ABRGameState* GetMatch() const;
    void RefreshLobby();
    void StartRound();
    void TickRound();
    void ResolveOutcome();
    void FinishRound(int32 Winner, bool bDrawResult);

    TWeakObjectPtr<ABRController> Players[2];
    FTimerHandle RoundTimer;
    double RoundStartTime = 0.0;
    double NextDamageTime = 0.0;
    bool bOutcomeQueued = false;
};
