#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BRTypes.h"
#include "BRLoot.generated.h"

class ABRCharacter;
class USceneComponent;
class UStaticMeshComponent;

/** A replicated pickup with one atomic, authority-only transfer. */
UCLASS()
class BATTLEROYALE_API ABRLoot : public AActor
{
    GENERATED_BODY()

public:
    ABRLoot();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    /** Authority initializes the world item and compatible ammunition amount. */
    void Configure(EBRItem InItem, int32 InAmount);

    /** Authority attempts one transfer and destroys the pickup on success. */
    bool TryCollect(ABRCharacter* Player);

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY(ReplicatedUsing=OnRep_Item) EBRItem Item = EBRItem::AK47;
    UPROPERTY(Replicated) int32 Amount = 1;
    UPROPERTY() TObjectPtr<USceneComponent> Root;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    bool bCollected = false;

    UFUNCTION() void OnRep_Item();
};
