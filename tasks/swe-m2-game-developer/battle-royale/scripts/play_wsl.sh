#!/usr/bin/env bash
set -euo pipefail

stage=4
if [[ ${1:-} == --stage && $# -ge 2 ]]; then
    stage=$2
    shift 2
fi

role=${1:-play}
if [[ ! "$stage" =~ ^([1-4]|sonnet|practice|covered|route|opponents|dashboard|opening-pilot)$ || ! "$role" =~ ^(play|host|guest)$ || $# -gt 2 ]] ||
   [[ "$stage" =~ ^(practice|covered|route|opponents|dashboard|opening-pilot)$ && "$role" != play ]]; then
    echo "Usage: bash $0 [--stage 1|2|3|4|sonnet|practice|covered|route|opponents|dashboard|opening-pilot] [play|host|guest] [extracted Linux directory]" >&2
    exit 2
fi

script=$(realpath -- "${BASH_SOURCE[0]}")
task_root=$(cd -- "$(dirname -- "$script")/.." && pwd)
stage4_install="$task_root/experiment/step04-reference/live-results/6efb3d19/play/Basin-Signal/Linux"
downloads="$task_root/experiment/dashboard-previews/live-results/7166aa9d"
practice_results="$task_root/experiment/practice-match/live-results"
practice_original="$practice_results/b04ee783/Basin-Signal-Stage-Practice/Linux"
case "$stage" in
    1) default_install="$task_root/experiment/local-game-runtime-light-fix/live-results/de2a0309/Basin-Signal/Linux" ;;
    2|3) default_install="$downloads/0$stage/play/Basin-Signal-Stage-0$stage/Linux" ;;
    4) default_install="$stage4_install" ;;
    sonnet)
        default_install="$task_root/experiment/model-evaluation/live-results/707f9bef/Battle-Royale-Duel/Linux"
        ;;
    practice)
        release="$practice_results/933a9674"
        updated="$release/Basin-Signal-Stage-Practice/Linux"
        default_install="$practice_original"
        if [[ -s "$release/release.json" && -x "$updated/BattleRoyale.sh" && -x "$updated/play-practice.sh" ]]; then
            default_install="$updated"
        fi
        ;;
    covered)
        release="$task_root/experiment/route-choice/live-results/ef33c499"
        default_install="$release/verified/Basin-Signal-Stage-Practice-Opening/Linux"
        ;;
    route)
        release="$task_root/experiment/route-choice/live-results/e1069683"
        default_install="$release/verified/Basin-Signal-Stage-Practice-Route-Rotation/Linux"
        ;;
    opponents)
        release="$task_root/experiment/route-choice/live-results/a28cfcee"
        default_install="$release/verified/Basin-Signal-Stage-Practice-Opponent-Search/Linux"
        ;;
    dashboard)
        release="$task_root/experiment/practice-match/dashboard-preview-editor-cleanup/live-results/4d030d3e"
        default_install="$release/verified/Basin-Signal-Stage-Dashboard-Practice/Linux"
        combined="$task_root/experiment/route-choice/live-results/d20a9ba3"
        updated="$combined/verified/Basin-Signal-Stage-Opponent-Search-Dashboard/Linux"
        if [[ -s "$combined/release.json" && -x "$updated/BattleRoyale.sh" ]]; then
            default_install="$updated"
        fi
        ;;
    opening-pilot)
        release="$task_root/experiment/feedback-comparison/prebuilt-inputs/oracle-verified"
        default_install="$release/verified/Basin-Signal-Stage-Opening-Feedback-Pilot/Linux"
        ;;
esac
install_dir=${2:-"$default_install"}
if [[ ! -x "$install_dir/BattleRoyale.sh" ]]; then
    echo "Could not find the Stage $stage game at $install_dir. Pass the extracted Linux directory after $role." >&2
    exit 2
fi

if [[ -z ${DISPLAY:-} && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
fi
if [[ -z ${DISPLAY:-} && -z ${WAYLAND_DISPLAY:-} ]]; then
    echo "No graphical display is available. Open the game from a WSL terminal with WSLg." >&2
    exit 1
fi

cd -- "$install_dir"
state="$PWD/.basin-wsl"

configure_audio() {
    local audio_libs="$state/audio/usr/lib/x86_64-linux-gnu"
    if [[ ! -f "$audio_libs/libpulse.so.0" ]]; then
        audio_libs="$stage4_install/.basin-wsl/audio/usr/lib/x86_64-linux-gnu"
    fi
    if [[ -f "$audio_libs/libpulse.so.0" && -S /mnt/wslg/PulseServer ]]; then
        export SDL_AUDIO_DRIVER="${SDL_AUDIO_DRIVER:-pulseaudio}"
        export LD_LIBRARY_PATH="$audio_libs:$audio_libs/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    fi
}

if [[ "$stage" =~ ^(practice|covered|route|opponents)$ ]]; then
    if [[ ! -x ./play-practice.sh ]]; then
        echo "The practice launcher is missing from $PWD." >&2
        exit 2
    fi
    configure_audio
    local_launcher="$task_root/experiment/practice-match/play-practice.sh"
    if [[ "$install_dir" == "$practice_original" && -f "$local_launcher" ]]; then
        exec bash "$local_launcher" --wsl "$PWD"
    fi
    exec ./play-practice.sh --wsl
fi

quality=(
    'sg.ViewDistanceQuality 0' 'sg.AntiAliasingQuality 0' 'sg.ShadowQuality 0'
    'sg.GlobalIlluminationQuality 0' 'sg.ReflectionQuality 0' 'sg.PostProcessQuality 0'
    'sg.EffectsQuality 0' 'sg.FoliageQuality 0' 'sg.ShadingQuality 0' 'sg.ResolutionQuality 50'
)
quality_commands=$(IFS=,; printf '%s' "${quality[*]}")
graphics=(-vulkan -AllowCPUDevices -windowed -ResX=640 -ResY=360 -WinY=60 -NoSplash "-ExecCmds=$quality_commands")

if [[ "$stage" == dashboard || "$stage" == opening-pilot ]]; then
    mkdir -p -- "$state"
    player_state=$(mktemp -d "$state/${stage}.XXXXXXXX")
    configure_audio
    export LP_NUM_THREADS=4
    echo "Press P in the game window to start solo practice."
    exec ./BattleRoyale.sh "${graphics[@]}" "-UserDir=$player_state" "-ABSLOG=$player_state/launch.log"
fi

if [[ "$role" == play ]]; then
    mkdir -p -- "$state/host" "$state/guest"
    : > "$state/host/launch.log"
    : > "$state/guest/launch.log"

    stop_players() {
        for pid in "${host_pid:-}" "${guest_pid:-}"; do
            if [[ -n "$pid" ]]; then
                kill -TERM -- "-$pid" 2>/dev/null || true
            fi
        done
        wait || true
    }

    trap stop_players EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    if [[ "$stage" == sonnet ]]; then
        echo "Opening the Stage 1 Sonnet lobby. The second window joins automatically."
        echo "Click Ready in both windows once the lobby shows two players."
    else
        echo "Opening two Stage $stage game windows. First launch can take about a minute."
        if [[ "$stage" != 4 ]]; then
            echo "In the left window press F1 to host. When its lobby appears, press F2 in the right window."
        fi
        echo "Press Enter in both windows to ready up."
        if [[ "$stage" == 3 || "$stage" == 4 ]]; then
            echo "Choose F3 or F4 in each window and press Enter to confirm deployment."
        fi
    fi
    setsid bash "$script" --stage "$stage" host "$PWD" > "$state/host/terminal.log" 2>&1 &
    host_pid=$!
    setsid bash "$script" --stage "$stage" guest "$PWD" > "$state/guest/terminal.log" 2>&1 &
    guest_pid=$!

    if wait -n "$host_pid" "$guest_pid"; then
        exit 0
    else
        status=$?
        echo "A game window closed with status $status. See $state/{host,guest}/terminal.log." >&2
        exit "$status"
    fi
fi

player_state="$state/$role"
mkdir -p -- "$player_state"
: > "$player_state/launch.log"
if [[ "$stage" == 4 && "$role" == guest ]]; then
    echo "Waiting for the host to render the lobby."
    host_log="$state/host/launch.log"
    deadline=$((SECONDS + 120))
    until grep -Fq 'BRServerClient event=state player=1 round=0' "$host_log" 2>/dev/null; do
        if (( SECONDS >= deadline )); then
            echo "The host lobby did not start. See $host_log." >&2
            exit 1
        fi
        sleep 1
    done
fi

case "$role" in
    host) launch=(-port=7777 -MULTIHOME=127.0.0.1 -WinX=20) ;;
    guest) launch=(-BRAddress=127.0.0.1:7777 -WinX=700) ;;
esac
if [[ "$stage" == 4 ]]; then
    case "$role" in
        host) launch=("/Engine/Maps/Entry?listen" "${launch[@]}" -BRServerCalibration) ;;
        guest) launch=(127.0.0.1:7777 -WinX=700 -BRServerCalibration) ;;
    esac
fi
if [[ "$stage" == sonnet ]]; then
    case "$role" in
        host) launch+=(-BRHost -PlayerName=Host) ;;
        guest)
            host_log="$state/host/launch.log"
            host_port=
            deadline=$((SECONDS + 120))
            while [[ -z "$host_port" ]]; do
                if [[ -s "$host_log" ]]; then
                    host_port=$(sed -nE 's/.*IpNetDriver listening on port ([0-9]+).*/\1/p' "$host_log" | tail -n 1)
                fi
                if [[ -z "$host_port" ]]; then
                    if (( SECONDS >= deadline )); then
                        echo "The Sonnet host did not open a listen port. See $host_log." >&2
                        exit 1
                    fi
                    sleep 1
                fi
            done
            launch=("-BRJoin=127.0.0.1:$host_port" -WinX=700 -PlayerName=Guest)
            ;;
    esac
fi

configure_audio
export LP_NUM_THREADS=4
exec ./BattleRoyale.sh "${launch[@]}" "${graphics[@]}" \
    "-UserDir=$player_state" "-ABSLOG=$player_state/launch.log"
