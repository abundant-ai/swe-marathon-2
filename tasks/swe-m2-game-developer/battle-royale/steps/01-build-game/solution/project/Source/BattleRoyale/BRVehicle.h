#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BRVehicle.generated.h"

class ABRCharacter;
class UBoxComponent;
class UStaticMesh;
class UStaticMeshComponent;

UCLASS()
class BATTLEROYALE_API ABRVehicle final : public AActor
{
    GENERATED_BODY()

public:
    ABRVehicle();

    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    bool TryEnter(ABRCharacter* Character);
    bool TryExit(ABRCharacter* Character, bool bForce = false);
    void SetDriveInput(ABRCharacter* Character, float Throttle, float Steering, bool bBrake);

    ABRCharacter* GetDriver() const { return Driver; }
    float GetForwardSpeed() const { return ForwardSpeed; }
    FVector GetDriverSeatOffset() const { return FVector(-35.0, -26.0, 48.0); }
    static constexpr float RideHeight = 76.0f;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UStaticMeshComponent* AddPart(const FName& Name, UStaticMesh* Mesh,
        const FVector& Center, const FVector& Size, const FRotator& Rotation = FRotator::ZeroRotator);
    TOptional<FVector> FindExit(const ABRCharacter& Character) const;
    void ResetControls();
    void Drive(float Seconds);

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UBoxComponent> Collision;

    UPROPERTY(Replicated)
    TObjectPtr<ABRCharacter> Driver;

    UPROPERTY(Replicated)
    float ForwardSpeed = 0.0f;

    float DriveThrottle = 0.0f;
    float DriveSteering = 0.0f;
    bool bDriveBrake = false;
    double LastDriveInputTime = 0.0;
    TArray<TPair<UStaticMeshComponent*, FLinearColor>> Paint;
};
