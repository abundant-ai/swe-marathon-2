#pragma once

#include "CoreMinimal.h"
#include "BRTypes.h"
#include "GameFramework/PlayerController.h"
#include "BRController.generated.h"

UCLASS()
class BATTLEROYALE_API ABRController : public APlayerController
{
    GENERATED_BODY()

public:
    int32 GetLocalSlot() const { return Slot; }
    bool IsLocalReady() const { return bReady; }
    bool IsInventoryOpen() const { return bShowInventory; }

    void SetSlot(int32 NewSlot);
    void SetReady(bool bNewReady);

    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
    virtual void BeginPlay() override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;

private:
    UPROPERTY(ReplicatedUsing=OnRep_Slot)
    int32 Slot = INDEX_NONE;

    UPROPERTY(Replicated)
    bool bReady = false;

    bool bShowInventory = false;
    bool bAutoReady = false;
    int32 LastReadySerial = INDEX_NONE;
    int32 LastFreshSerial = INDEX_NONE;
    int32 LastObservedSerial = INDEX_NONE;
    EBRMatchPhase LastObservedPhase = EBRMatchPhase::Waiting;
    double PhaseObservedAt = 0.0;

    UFUNCTION()
    void OnRep_Slot();

    UFUNCTION(Server, Reliable)
    void ServerToggleReady();

    void HostMatch();
    void JoinMatch();
    void ToggleReady();
    void ToggleInventory();
};
