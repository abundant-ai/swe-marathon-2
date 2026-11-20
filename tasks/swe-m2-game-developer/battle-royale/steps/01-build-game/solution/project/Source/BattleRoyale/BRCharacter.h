#pragma once

#include "CoreMinimal.h"
#include "Engine/NetSerialization.h"
#include "GameFramework/Character.h"
#include "BRTypes.h"
#include "BRCharacter.generated.h"

class ABRVehicle;
class UCameraComponent;
class UInputComponent;
class UPointLightComponent;
class USceneComponent;
class USpringArmComponent;
class UStaticMeshComponent;

/** A human-controlled pawn with server-owned health, inventory, and actions. */
UCLASS()
class BATTLEROYALE_API ABRCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ABRCharacter();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    /** Authority resets the player's match state, including movement and inventory. */
    void ResetForMatch();

    /** Authority applies a finite, positive quantity of fictional gameplay damage. */
    void ApplyAuthorityDamage(float Damage);

    bool IsEliminated() const { return Health <= 0.0f; }
    float GetHealth() const { return Health; }
    bool OwnsRifle(EBRRifle Rifle) const;
    int32 GetLoadedAmmo(EBRRifle Rifle) const;
    int32 GetReserveAmmo(EBRRifle Rifle) const;
    EBRRifle GetEquippedRifle() const { return EquippedRifle; }
    bool IsReloading() const { return ReloadEndTime > 0.0f; }
    float GetReloadEndTime() const { return ReloadEndTime; }
    bool IsAiming() const { return bAiming; }
    FString GetActionFeedback() const;
    ABRVehicle* GetVehicle() const;

    /** Authority mounts at the vehicle's seat or detaches at the current world position. */
    void SetVehicle(ABRVehicle* NewVehicle);

    /** Authority accepts a world loot item if the player can use it. */
    bool TryGiveItem(EBRItem Item, int32 Amount);

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;

private:
    UPROPERTY(ReplicatedUsing=OnRep_Health) float Health = 100.0f;
    UPROPERTY(Replicated) bool bOwnsAK47 = false;
    UPROPERTY(Replicated) bool bOwnsM16 = false;
    UPROPERTY(Replicated) int32 AKLoaded = 0;
    UPROPERTY(Replicated) int32 M16Loaded = 0;
    UPROPERTY(Replicated) int32 AKReserve = 0;
    UPROPERTY(Replicated) int32 M16Reserve = 0;
    UPROPERTY(ReplicatedUsing=OnRep_Equipped) EBRRifle EquippedRifle = EBRRifle::None;
    UPROPERTY(Replicated) float ReloadEndTime = 0.0f;
    UPROPERTY(Replicated) bool bSprinting = false;
    UPROPERTY(Replicated) bool bAiming = false;
    UPROPERTY(Replicated) float RecoilPeak = 0.0f;
    UPROPERTY(Replicated) float LastRecoilShotTime = 0.0f;
    UPROPERTY(ReplicatedUsing=OnRep_Vehicle) TObjectPtr<ABRVehicle> Vehicle;
    UPROPERTY(Replicated) FString ActionFeedback;
    UPROPERTY(Replicated) float FeedbackEndTime = 0.0f;

    UPROPERTY() TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<USceneComponent> Model;
    UPROPERTY() TObjectPtr<USceneComponent> Weapon;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> BodyMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> WeaponMeshes;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> LeftLeg;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> RightLeg;
    UPROPERTY() TObjectPtr<UPointLightComponent> MuzzleFlash;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> SurfaceImpact;
    UPROPERTY() TObjectPtr<UPointLightComponent> SurfaceImpactLight;

    bool bTriggerHeld = false;
    bool bAutomaticFire = false;
    bool bBraking = false;
    float EquipReadyTime = 0.0f;
    float NextShotTime = 0.0f;
    float DriveThrottle = 0.0f;
    float DriveSteering = 0.0f;
    float NextDriveTime = 0.0f;
    float NextServerDriveTime = 0.0f;
    float NextInteractionTime = 0.0f;
    float FlashEndTime = 0.0f;
    float SurfaceImpactEndTime = 0.0f;
    float GaitTime = 0.0f;

    UFUNCTION() void OnRep_Health();
    UFUNCTION() void OnRep_Equipped();
    UFUNCTION() void OnRep_Vehicle();

    bool CanPlay() const;
    float MatchTime() const;
    void SetActionFeedback(const TCHAR* Text);
    void CancelWeaponActions();
    void UpdatePresentation(float DeltaSeconds);
    void RefreshMovement();
    float RecoilAt(float Now) const;
    FRotator AimInputRotation() const;
    FRotator ShotAim(float Now) const;
    void TryFire();
    void FinishReload();

    void MoveForward(float Value);
    void MoveRight(float Value);
    void LookYaw(float Value);
    void LookPitch(float Value);
    void StartJump();
    void EndJump();
    void StartSprint();
    void EndSprint();
    void StartFire();
    void EndFire();
    void StartAim();
    void EndAim();
    void RequestReload();
    void SelectAK47();
    void SelectM16();
    void RequestInteract();
    void StartBrake();
    void EndBrake();

    UFUNCTION(Server, Reliable) void ServerSetSprint(bool bEnabled);
    UFUNCTION(Server, Reliable) void ServerSetFire(bool bPressed);
    UFUNCTION(Server, Reliable) void ServerSetAim(bool bEnabled);
    UFUNCTION(Server, Reliable) void ServerEquip(EBRRifle Rifle);
    UFUNCTION(Server, Reliable) void ServerReload();
    UFUNCTION(Server, Reliable) void ServerInteract();
    UFUNCTION(Server, Unreliable) void ServerDrive(float Throttle, float Steering, bool bBrake);
    UFUNCTION(NetMulticast, Unreliable) void MulticastShot(
        FVector_NetQuantize Origin, FVector_NetQuantize End, bool bHit,
        FVector_NetQuantizeNormal SurfaceNormal, EBRRifle Rifle);
};
