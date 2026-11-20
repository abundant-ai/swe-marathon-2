#pragma once

#include <algorithm>

namespace BRWeapon
{
    struct FRifleTuning
    {
        int Capacity;
        float Damage;
        float Interval;
        float ReloadSeconds;
        float RecoilDegrees;
        float HipSpreadDegrees;
        float SightSpreadDegrees;
    };

    inline constexpr FRifleTuning AK {18, 24.0f, 0.15f, 1.75f, 1.30f, 2.0f, .45f};
    inline constexpr FRifleTuning M16 {24, 17.0f, 0.25f, 1.45f, .65f, 1.25f, .25f};
    inline constexpr float RecoilHoldSeconds = .28f;
    inline constexpr float RecoilRecoverySeconds = .32f;
    inline constexpr float MaxRecoilDegrees = 12.0f;

    constexpr float SpreadDegrees(const FRifleTuning& Rifle, bool bAiming)
    {
        return bAiming ? Rifle.SightSpreadDegrees : Rifle.HipSpreadDegrees;
    }

    constexpr float RecoilAt(float Peak, float SecondsSinceShot)
    {
        const float Recovery = (SecondsSinceShot - RecoilHoldSeconds) / RecoilRecoverySeconds;
        return Peak * (1.0f - std::clamp(Recovery, 0.0f, 1.0f));
    }

    constexpr float RecoilAfterShot(float Current, const FRifleTuning& Rifle, bool bAiming)
    {
        const float Kick = Rifle.RecoilDegrees * (bAiming ? .73f : 1.0f);
        return std::min(Current + Kick, MaxRecoilDegrees);
    }
}
