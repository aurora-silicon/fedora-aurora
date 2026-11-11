#!/bin/bash
#
# firefox-update.sh - Update the Firefox package in Fedora rawhide to a new
#                     upstream version.
#
# This is a shell implementation of the "firefox-update" skill
# (see Update-SKILL.md). It performs the mechanical steps of the update;
# steps which need human judgement (patch rebasing, build failure analysis)
# stop the script with a description of what has to be done manually.
#
# Usage: ./firefox-update.sh <version> [options]
#
set -o pipefail

#-----------------------------------------------------------------------------
# Configuration / defaults
#-----------------------------------------------------------------------------

FEDORA_BASE_DIR="${FEDORA_BASE_DIR:-$PWD}"
CHANGELOG_AUTHOR="${CHANGELOG_AUTHOR:-}"
ARCHIVE_URL="https://archive.mozilla.org/pub/firefox/candidates"

NEW_VERSION=""
OLD_VERSION=""
BUILD_VERSION=""
PACKAGE_DIR=""
LANGPACK_FILE=""
NEW_TARBALL=""
NSS_VERSION=""
NSPR_VERSION=""
OLD_NSS_VERSION=""
OLD_NSPR_VERSION=""

RESUME_FROM=1
ASSUME_YES=0
DROP_PATCHES=()
DROPPED_PATCHES=()
ADD_PATCHES=()
ADDED_PATCHES=()
CHANGELOG_MSG=""
DO_LOCAL_BUILD=0
DO_PUSH=0
DO_UPLOAD=1
DO_ROLLBACK=0
SPEC_NOTES=()

#-----------------------------------------------------------------------------
# Output helpers
#-----------------------------------------------------------------------------

if [ -t 1 ]; then
    C_BOLD=$'\e[1m'; C_RED=$'\e[31m'; C_GREEN=$'\e[32m'
    C_YELLOW=$'\e[33m'; C_BLUE=$'\e[34m'; C_OFF=$'\e[0m'
else
    C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_OFF=""
fi

CURRENT_STEP=0

step() {
    CURRENT_STEP="$1"; shift
    printf '\n%s==> Step %s: %s...%s\n' "$C_BOLD$C_BLUE" "$CURRENT_STEP" "$*" "$C_OFF"
}

ok()   { printf '%s✅ %s%s\n' "$C_GREEN" "$*" "$C_OFF"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '%s⚠️  %s%s\n' "$C_YELLOW" "$*" "$C_OFF" >&2; }

die() {
    printf '\n%s❌ ERROR: %s%s\n' "$C_RED" "$*" "$C_OFF" >&2
    if [ "$CURRENT_STEP" -gt 0 ]; then
        printf '%sFix the problem and resume with: %s %s --resume %s%s\n' \
            "$C_YELLOW" "$0" "$NEW_VERSION" "$CURRENT_STEP" "$C_OFF" >&2
    fi
    exit 1
}

run() {
    printf '%s$ %s%s\n' "$C_BOLD" "$*" "$C_OFF"
    "$@"
}

# confirm "question" [default_yes]
confirm() {
    local question="$1" default="${2:-n}" answer
    if [ "$ASSUME_YES" -eq 1 ]; then
        info "$question -> yes (--yes)"
        return 0
    fi
    if [ ! -t 0 ]; then
        info "$question -> $default (not a terminal)"
        [ "$default" = "y" ]
        return
    fi
    while true; do
        if [ "$default" = "y" ]; then
            read -r -p "$C_BOLD$question [Y/n] $C_OFF" answer
            answer="${answer:-y}"
        else
            read -r -p "$C_BOLD$question [y/N] $C_OFF" answer
            answer="${answer:-n}"
        fi
        case "${answer,,}" in
            y|yes) return 0 ;;
            n|no)  return 1 ;;
            *)     echo "Please answer yes or no." ;;
        esac
    done
}

ask() {
    local question="$1" answer
    [ -t 0 ] || die "Need an answer for: $question (run interactively or pass it as an option)"
    read -r -p "$C_BOLD$question $C_OFF" answer
    printf '%s' "$answer"
}

# Steps below RESUME_FROM are skipped.
skip_step() {
    [ "$1" -lt "$RESUME_FROM" ]
}

#-----------------------------------------------------------------------------
# Usage
#-----------------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") <version> [options]

Updates the Firefox package in Fedora rawhide to <version> (e.g. 157.0).

<version> may be omitted when --resume N is given with N > 1: the version
is then read from the Version: tag already written to firefox.spec.

Options:
  --resume N          Skip to step N (1-14), reading current on-disk state
  -n                  Shorthand for --resume 11 (detect NSS/NSPR versions)
  --build buildN      Use this Mozilla candidate build instead of the latest
  --dir PATH          Package directory (default: \$PWD if it holds firefox.spec,
                      otherwise \$FEDORA_BASE_DIR/firefox)
  -d, --drop-patch P  Drop a patch that is no longer needed: removes its
                      PatchNNN: and %patch -PNNN lines from firefox.spec and
                      deletes the file from git. P is the patch file name or
                      its number. May be given more than once.
  -a, --add-patch F   Add an upstream patch already sitting in the package
                      directory as file F (it is not copied there): assigns
                      it the next free PatchNNN:, appends the matching
                      %patch -PNNN line, and stages the file with git. May
                      be given more than once. Review the generated %patch
                      line (ordering, -p level, backup suffix) before
                      committing.
  -c, --changelog MSG Add a %changelog entry and bump Release:. Without a
                      <version> (i.e. combined with -a/-d only) this is the
                      only way to bump the release; with a <version> it
                      overrides the default "Update to latest upstream" entry.
  --local             Run 'fedpkg local' (step 12); takes 1-2 hours
  --push              Push to Fedora dist-git when finished (step 14)
  --no-upload         In step 8 do not upload to the lookaside cache (for
                      users without upload permission for the Firefox
                      tarball). The sources file is still updated, with
                      checksums computed locally, and the command for
                      someone with permission is printed.
  --yes               Answer yes to all questions (non-interactive)
  --rollback          Discard the in-progress update and clean up, then exit
  -h, --help          Show this help

Environment:
  FEDORA_BASE_DIR     Base directory holding the dist-git clones
  CHANGELOG_AUTHOR    "Name <email>" used for the %changelog entry

Steps:
   1 Get version info          8 Upload new sources
   2 Set up package directory  9 Check and rebase patches (manual)
   3 Pull latest rawhide      10 Verify patches with fedpkg prep
   4 Bump version in spec     11 Detect NSS/NSPR versions from the tarball
   5 Get Mozilla build number 12 Local build (optional)
   6 Download source tarball  13 Commit the update
   7 Download langpacks       14 Summary and push

The NSS and NSPR requirements are always taken from the Firefox sources in
step 11 and written to firefox.spec - the script never asks for them.
EOF
}

#-----------------------------------------------------------------------------
# Argument parsing
#-----------------------------------------------------------------------------

while [ $# -gt 0 ]; do
    case "$1" in
        --resume)   RESUME_FROM="$2"; shift 2 ;;
        -r=*)       RESUME_FROM="${1#*=}"; shift ;;
        --resume=*) RESUME_FROM="${1#*=}"; shift ;;
        -n)         RESUME_FROM=11; shift ;;
        --build)    BUILD_VERSION="$2"; shift 2 ;;
        --build=*)  BUILD_VERSION="${1#*=}"; shift ;;
        --dir)      PACKAGE_DIR="$2"; shift 2 ;;
        --dir=*)    PACKAGE_DIR="${1#*=}"; shift ;;
        -d|--drop-patch) DROP_PATCHES+=("$2"); shift 2 ;;
        -d=*)            DROP_PATCHES+=("${1#*=}"); shift ;;
        --drop-patch=*)  DROP_PATCHES+=("${1#*=}"); shift ;;
        -a|--add-patch)  ADD_PATCHES+=("$2"); shift 2 ;;
        -a=*)            ADD_PATCHES+=("${1#*=}"); shift ;;
        --add-patch=*)   ADD_PATCHES+=("${1#*=}"); shift ;;
        -c|--changelog)  CHANGELOG_MSG="$2"; shift 2 ;;
        -c=*)            CHANGELOG_MSG="${1#*=}"; shift ;;
        --changelog=*)   CHANGELOG_MSG="${1#*=}"; shift ;;
        --local)    DO_LOCAL_BUILD=1; shift ;;
        --push)     DO_PUSH=1; shift ;;
        --no-upload) DO_UPLOAD=0; shift ;;
        --yes|-y)   ASSUME_YES=1; shift ;;
        --rollback) DO_ROLLBACK=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        -*)         usage >&2; die "Unknown option: $1" ;;
        *)
            [ -z "$NEW_VERSION" ] || die "Unexpected argument: $1"
            NEW_VERSION="$1"; shift ;;
    esac
done

case "$RESUME_FROM" in
    ''|*[!0-9]*) die "--resume needs a step number (1-14)" ;;
esac
[ "$RESUME_FROM" -ge 1 ] && [ "$RESUME_FROM" -le 14 ] || die "--resume must be 1-14"

#-----------------------------------------------------------------------------
# Preflight
#-----------------------------------------------------------------------------

for tool in fedpkg rpmdev-bumpspec git wget curl python3 rpmspec; do
    command -v "$tool" >/dev/null 2>&1 || die "Required tool not found: $tool"
done

# Ensure a usable Fedora Kerberos ticket, otherwise fedpkg calls fail later on.
check_kerberos() {
    local principal
    principal=$(klist -l 2>/dev/null | awk '/FEDORAPROJECT\.ORG/ {print $1; exit}')
    if [ -n "$principal" ] && klist -s 2>/dev/null; then
        info "Kerberos principal: $principal"
        return 0
    fi
    if [ -n "$principal" ]; then
        die "Kerberos ticket for $principal is missing or expired. Run: kinit $principal"
    fi
    die "No FEDORAPROJECT.ORG Kerberos ticket found. Run: kinit <username>@FEDORAPROJECT.ORG"
}

spec_get() {  # spec_get <tag-or-macro-regexp> -- first capture of the value
    grep -m1 -oP "$1" firefox.spec 2>/dev/null
}

# drop_patch <patch-file-name | patch-number>
# Removes the PatchNNN: declaration and the matching '%patch -PNNN' line from
# firefox.spec, then deletes the patch file from git.
drop_patch() {
    local want="$1" num file
    if [[ "$want" =~ ^[0-9]+$ ]]; then
        num="$want"
        file=$(grep -m1 -oP "^Patch${num}:[[:space:]]*\K\S+" firefox.spec)
        [ -n "$file" ] || die "No 'Patch${num}:' line in firefox.spec"
    else
        file="$want"
        num=$(awk -v f="$file" \
            '$1 ~ /^Patch[0-9]*:$/ && $2 == f { sub(/^Patch/,"",$1); sub(/:$/,"",$1); print $1; exit }' \
            firefox.spec)
        [ -n "$num" ] || die "Patch '$file' is not referenced by firefox.spec"
    fi

    info "Dropping Patch${num}: $file"

    sed -i -E "/^Patch${num}:[[:space:]]/d" firefox.spec \
        || die "Cannot remove the Patch${num}: line"
    grep -qE "^Patch${num}:[[:space:]]" firefox.spec \
        && die "Patch${num}: is still in firefox.spec"

    # '-P44' must not match '-P440', hence the trailing boundary.
    if grep -qE "^%patch[[:space:]]+-P${num}([[:space:]]|$)" firefox.spec; then
        sed -i -E "/^%patch[[:space:]]+-P${num}([[:space:]]|$)/d" firefox.spec \
            || die "Cannot remove the '%patch -P${num}' line"
        grep -qE "^%patch[[:space:]]+-P${num}([[:space:]]|$)" firefox.spec \
            && die "'%patch -P${num}' is still in firefox.spec"
    else
        warn "No '%patch -P${num}' line found - only the declaration was removed."
    fi

    if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
        run git rm -f -- "$file" || die "git rm of $file failed"
    elif [ -f "$file" ]; then
        info "$file is not tracked by git, removing it from disk"
        rm -f -- "$file"
    else
        warn "$file does not exist on disk - only firefox.spec was changed."
    fi

    DROPPED_PATCHES+=("$file (Patch${num})")
    SPEC_NOTES+=("Dropped Patch${num}: $file")
}

# add_patch <patch-file-already-in-the-package-dir>
# The file must already exist in the package directory (it is not copied
# from elsewhere). Assigns it the next free PatchNNN:, appends the
# declaration and the matching '%patch -PNNN' line to firefox.spec, and
# stages the file with git. The new %patch line is only a starting point -
# patch ordering, -p level and backup suffix may need manual adjustment.
add_patch() {
    local src="$1" base num short last_decl last_apply
    base=$(basename -- "$src")

    [ -f "$base" ] \
        || die "$base not found in $PACKAGE_DIR - place the patch file there first (it is not copied)"

    grep -qE "^Patch[0-9]*:[[:space:]]+${base}([[:space:]]|$)" firefox.spec \
        && die "$base is already referenced by firefox.spec"

    num=$(grep -oP '^Patch\K[0-9]+(?=:)' firefox.spec | sort -n | tail -1)
    [ -n "$num" ] || die "No existing Patch declarations found in firefox.spec to number from"
    num=$((num + 1))
    while grep -qE "^Patch${num}:[[:space:]]" firefox.spec; do
        num=$((num + 1))
    done

    info "Adding $base as Patch${num}"

    last_decl=$(grep -nE '^Patch[0-9]*:[[:space:]]' firefox.spec | tail -1 | cut -d: -f1)
    [ -n "$last_decl" ] || die "No 'PatchNNN:' line found to insert the new one after"
    sed -i "${last_decl}a Patch${num}:        ${base}" firefox.spec \
        || die "Cannot insert the Patch${num}: line"
    grep -qE "^Patch${num}:[[:space:]]+${base}([[:space:]]|$)" firefox.spec \
        || die "Patch${num}: was not added to firefox.spec"

    short="${base%.patch}"; short=$(printf '%s' "$short" | tr -cs 'A-Za-z0-9' '-')
    last_apply=$(grep -nE '^%patch[[:space:]]+-P[0-9]+' firefox.spec | tail -1 | cut -d: -f1)
    if [ -n "$last_apply" ]; then
        sed -i "${last_apply}a %patch -P${num} -p1 -b .${short}" firefox.spec \
            || die "Cannot insert the '%patch -P${num}' line"
        grep -qE "^%patch[[:space:]]+-P${num}([[:space:]]|$)" firefox.spec \
            || die "'%patch -P${num}' was not added to firefox.spec"
    else
        warn "No existing '%patch -P...' line found - add '%patch -P${num} -p1' to %prep by hand."
    fi

    run git add -- "$base" || die "git add of $base failed"

    ADDED_PATCHES+=("$base (Patch${num})")
    SPEC_NOTES+=("Added Patch${num}: $base")
    warn "Review the new '%patch -P${num}' line (ordering, -p level, backup suffix) before committing."
}

#-----------------------------------------------------------------------------
# Step 1: Get version info
#-----------------------------------------------------------------------------

# -d/--drop-patch and/or -a/--add-patch without a version only edit the spec
# and git - no update is started, so no version is needed or asked for.
PATCH_ONLY=0
if [ -z "$NEW_VERSION" ] \
   && { [ "${#DROP_PATCHES[@]}" -gt 0 ] || [ "${#ADD_PATCHES[@]}" -gt 0 ]; }; then
    PATCH_ONLY=1
fi

if [ -z "$PACKAGE_DIR" ]; then
    if [ -f "$PWD/firefox.spec" ]; then
        PACKAGE_DIR="$PWD"
    else
        PACKAGE_DIR="$FEDORA_BASE_DIR/firefox"
    fi
fi

if [ -z "$NEW_VERSION" ] && [ "$PATCH_ONLY" -eq 0 ]; then
    # Resuming an in-progress update: the version was already bumped into
    # firefox.spec back in step 4, so read it from there instead of asking.
    if [ "$RESUME_FROM" -gt 1 ] && [ -f "$PACKAGE_DIR/firefox.spec" ]; then
        NEW_VERSION=$(grep -m1 -oP '^Version:\s*\K\S+' "$PACKAGE_DIR/firefox.spec")
        [ -n "$NEW_VERSION" ] \
            && info "No version given - using $NEW_VERSION from $PACKAGE_DIR/firefox.spec (--resume $RESUME_FROM)"
    fi
    if [ -z "$NEW_VERSION" ]; then
        NEW_VERSION=$(ask "What Firefox version would you like to update to? (e.g. 157.0)")
        [ -n "$NEW_VERSION" ] || die "No version given"
    fi
fi

if [ "$PATCH_ONLY" -eq 0 ]; then
    step 1 "Preparing update to Firefox $NEW_VERSION"
    info "Package directory: $PACKAGE_DIR"
    ok "Target version: $NEW_VERSION"
fi

#-----------------------------------------------------------------------------
# Step 2: Set up the package directory
#-----------------------------------------------------------------------------

if [ ! -d "$PACKAGE_DIR" ]; then
    step 2 "Cloning the firefox package"
    check_kerberos
    cd "$FEDORA_BASE_DIR" || die "Cannot enter $FEDORA_BASE_DIR"
    run fedpkg clone firefox || die "fedpkg clone firefox failed"
    ok "Cloned firefox into $PACKAGE_DIR"
fi

cd "$PACKAGE_DIR" || die "Cannot enter $PACKAGE_DIR"
[ -f firefox.spec ] || die "$PACKAGE_DIR does not contain firefox.spec"

#-----------------------------------------------------------------------------
# Patch-only mode: -d/--drop-patch and/or -a/--add-patch given without a
# version; -c/--changelog optionally bumps Release: and the %changelog.
#-----------------------------------------------------------------------------

if [ "$PATCH_ONLY" -eq 1 ]; then
    printf '\n%s==> Updating patches in firefox.spec in %s%s\n' \
        "$C_BOLD$C_BLUE" "$PACKAGE_DIR" "$C_OFF"
    for p in "${DROP_PATCHES[@]}"; do
        drop_patch "$p"
    done
    for p in "${ADD_PATCHES[@]}"; do
        add_patch "$p"
    done

    if [ -n "$CHANGELOG_MSG" ]; then
        bumpspec_args=(--comment "$CHANGELOG_MSG")
        [ -n "$CHANGELOG_AUTHOR" ] && bumpspec_args+=(--userstring "$CHANGELOG_AUTHOR")
        run rpmdev-bumpspec "${bumpspec_args[@]}" firefox.spec \
            || die "rpmdev-bumpspec failed"
        ok "Release bumped to $(spec_get '^Release:\s*\K\S+') and changelog entry added."
    else
        info "No --changelog given - Release: and %changelog left unchanged."
    fi

    if [ "${#DROPPED_PATCHES[@]}" -gt 0 ]; then
        printf '\n  Dropped patches:\n'
        printf '    - %s\n' "${DROPPED_PATCHES[@]}"
    fi
    if [ "${#ADDED_PATCHES[@]}" -gt 0 ]; then
        printf '\n  Added patches:\n'
        printf '    - %s\n' "${ADDED_PATCHES[@]}"
    fi
    printf '\n'
    ok "firefox.spec updated."
    info "Review with 'git diff' and commit when you are ready."
    exit 0
fi

#-----------------------------------------------------------------------------
# Report the state of the working tree before touching anything
#-----------------------------------------------------------------------------

# Prints the local changes as a diff; returns 0 when there are any.
# Untracked files are ignored on purpose - a normal run leaves downloaded
# tarballs lying around and those are not interesting here.
show_local_changes() {
    git diff --quiet HEAD 2>/dev/null && return 1
    printf '%sLocal changes in %s (branch %s):%s\n\n' \
        "$C_BOLD$C_YELLOW" "$PACKAGE_DIR" "$(git branch --show-current)" "$C_OFF"
    git --no-pager diff HEAD
    printf '\n'
    git --no-pager diff --stat HEAD | tail -1
    return 0
}

# Prints the diff that is about to be committed. Rebased patch files can make
# it huge, so anything longer than $DIFF_PREVIEW_LINES is only shown on request.
DIFF_PREVIEW_LINES=500

show_staged_diff() {
    if git diff --cached --quiet; then
        warn "Nothing is staged - there is no diff to review."
        return 1
    fi

    printf '\n%sDiff to be committed:%s\n\n' "$C_BOLD$C_YELLOW" "$C_OFF"
    git --no-pager diff --cached --stat

    local lines
    lines=$(git --no-pager diff --cached | wc -l)
    printf '\n'
    if [ "$lines" -le "$DIFF_PREVIEW_LINES" ]; then
        git --no-pager diff --cached
    else
        info "The diff has $lines lines."
        if confirm "Show the full diff?"; then
            git --no-pager diff --cached
        else
            info "Skipped; review it later with 'git diff --cached'."
        fi
    fi

    # Changes left out of the commit are easy to miss once fedpkg opens $EDITOR.
    if ! git diff --quiet; then
        printf '\n'
        warn "These tracked files are modified but NOT staged:"
        git --no-pager diff --name-only | sed 's/^/     /' >&2
    fi

    printf '\n'
    return 0
}

# Destructive prompts are never auto-answered by --yes; they always need a
# deliberate keystroke. Answering 'q' aborts the whole update.
confirm_destructive() {
    local question="$1" answer
    if [ ! -t 0 ]; then
        info "$question -> no (not a terminal)"
        return 1
    fi
    while true; do
        read -r -p "$C_BOLD$C_RED$question [y]es / [N]o / [q]uit $C_OFF" answer
        case "${answer,,}" in
            y|yes)  return 0 ;;
            n|no|"") return 1 ;;
            q|quit)
                printf '%sAborted - the working tree is left untouched.%s\n' \
                    "$C_YELLOW" "$C_OFF"
                exit 0 ;;
            *) echo "Please answer y, n or q." ;;
        esac
    done
}

# Offer to throw the local changes away before starting the update.
offer_reset_local_changes() {
    if [ "$RESUME_FROM" -gt 1 ]; then
        warn "Resuming at step $RESUME_FROM - the changes above are probably your"
        warn "in-progress update. Discarding them restarts the update from scratch."
    fi

    printf '\n'
    if confirm_destructive "Discard the local changes with 'git reset --hard HEAD'?"; then
        run git reset --hard HEAD || die "git reset --hard failed"
        ok "Local changes discarded."
    else
        info "Keeping the local changes."
    fi
}

printf '\n'
if show_local_changes; then
    HAVE_LOCAL_CHANGES=1
    [ "$DO_ROLLBACK" -eq 1 ] || offer_reset_local_changes
    # Re-check: the offer above may have reset the tree.
    git diff --quiet HEAD 2>/dev/null && HAVE_LOCAL_CHANGES=0
else
    HAVE_LOCAL_CHANGES=0
    ok "Working tree is clean."
fi

#-----------------------------------------------------------------------------
# Rollback mode
#-----------------------------------------------------------------------------

if [ "$DO_ROLLBACK" -eq 1 ]; then
    printf '\n%sRollback: discarding the in-progress update listed above%s\n' \
        "$C_BOLD$C_YELLOW" "$C_OFF"
    confirm "Reset the working tree to origin/rawhide and remove downloaded tarballs?" \
        || die "Rollback cancelled"
    run git checkout rawhide || die "git checkout rawhide failed"
    run git reset --hard origin/rawhide || die "git reset failed"
    rm -rf "firefox-$NEW_VERSION/"
    rm -f  "firefox-$NEW_VERSION.source.tar.xz"
    rm -f  firefox-langpacks-"$NEW_VERSION"-*.tar.xz
    ok "Rollback complete - the working tree is clean."
    exit 0
fi

#-----------------------------------------------------------------------------
# Step 3: Pull latest rawhide
#-----------------------------------------------------------------------------

if ! skip_step 3; then
    step 3 "Pulling latest rawhide"
    if [ "$HAVE_LOCAL_CHANGES" -eq 1 ]; then
        warn "The working tree has uncommitted changes (shown above)"
        confirm "Continue anyway?" || die "Aborted - clean the working tree first"
    fi
    if git show-ref --verify --quiet refs/heads/rawhide; then
        run git checkout rawhide || die "git checkout rawhide failed"
    else
        run git checkout -b rawhide origin/rawhide || die "Cannot create the rawhide branch"
    fi
    run git pull || die "git pull failed"
    ok "Working tree is up to date on rawhide."
fi

#-----------------------------------------------------------------------------
# Step 4: Bump the version in the SPEC file
#-----------------------------------------------------------------------------

OLD_NSS_VERSION=$(spec_get '^%global\s+nss_version\s+\K\S+')
OLD_NSPR_VERSION=$(spec_get '^%global\s+nspr_version\s+\K\S+')

if ! skip_step 4; then
    step 4 "Bumping the version in firefox.spec"
    OLD_VERSION=$(spec_get '^Version:\s*\K\S+')
    [ -n "$OLD_VERSION" ] || die "Cannot read Version: from firefox.spec"
    info "Current version: $OLD_VERSION"

    DO_BUMP=1
    if [ "$OLD_VERSION" = "$NEW_VERSION" ]; then
        warn "firefox.spec is already at $NEW_VERSION"
        if confirm "Bump it again (adds another changelog entry)?"; then
            DO_BUMP=1
        else
            DO_BUMP=0
            info "Keeping the spec version as is."
        fi
    fi

    if [ "$DO_BUMP" -eq 1 ]; then
        bumpspec_args=(--new "$NEW_VERSION" \
            --comment "${CHANGELOG_MSG:-Update to latest upstream ($NEW_VERSION)}")
        [ -n "$CHANGELOG_AUTHOR" ] && bumpspec_args+=(--userstring "$CHANGELOG_AUTHOR")
        run rpmdev-bumpspec "${bumpspec_args[@]}" firefox.spec \
            || die "rpmdev-bumpspec failed"
    fi

    got_version=$(spec_get '^Version:\s*\K\S+')
    [ "$got_version" = "$NEW_VERSION" ] \
        || die "Version: is $got_version, expected $NEW_VERSION - fix firefox.spec manually"

    got_release=$(spec_get '^Release:\s*\K\S+')
    if [[ "$got_release" != 1* ]]; then
        info "Release is '$got_release', resetting to 1%{?pre_tag}%{?dist}"
        sed -i -E 's|^Release:([[:space:]]*).*|Release:\11%{?pre_tag}%{?dist}|' firefox.spec \
            || die "Cannot reset Release:"
    fi
    ok "firefox.spec is at $NEW_VERSION, release $(spec_get '^Release:\s*\K\S+')."
fi

# Recover OLD_VERSION when resuming past step 4.
if [ -z "$OLD_VERSION" ]; then
    OLD_VERSION=$(git show HEAD:firefox.spec 2>/dev/null | grep -m1 -oP '^Version:\s*\K\S+')
    OLD_VERSION="${OLD_VERSION:-unknown}"
fi

#-----------------------------------------------------------------------------
# Step 5: Get the Mozilla build version
#-----------------------------------------------------------------------------

CANDIDATES_URL="$ARCHIVE_URL/$NEW_VERSION-candidates"

if [ -z "$BUILD_VERSION" ]; then
    step 5 "Looking up the latest Mozilla candidate build"
    listing=$(curl -fsSL "$CANDIDATES_URL/") \
        || die "Cannot list $CANDIDATES_URL/ - is $NEW_VERSION released yet?"
    BUILD_VERSION=$(grep -oE 'build[0-9]+/' <<<"$listing" | tr -d '/' | sort -u -V | tail -1)
    [ -n "$BUILD_VERSION" ] || die "No buildN directory found in $CANDIDATES_URL/"
    ok "Latest candidate build: $BUILD_VERSION"
else
    info "Using candidate build: $BUILD_VERSION (from --build)"
fi

BUILD_URL="$CANDIDATES_URL/$BUILD_VERSION"
# The source tarball and its .asc live in the source/ subdirectory, the
# langpack XPIs do not.
SOURCE_URL="$BUILD_URL/source"

#-----------------------------------------------------------------------------
# Step 6: Download the Firefox source tarball
#-----------------------------------------------------------------------------

NEW_TARBALL="firefox-$NEW_VERSION.source.tar.xz"

# Checks $NEW_TARBALL against the detached signature $NEW_TARBALL.asc.
#   0 = good signature, 1 = bad signature, 2 = cannot tell (no gpg / no key)
verify_tarball_signature() {
    command -v gpg >/dev/null 2>&1 || return 2
    [ -s "$NEW_TARBALL.asc" ] || return 2
    local out key
    out=$(gpg --verify "$NEW_TARBALL.asc" "$NEW_TARBALL" 2>&1)
    if grep -q '^gpg: Good signature' <<<"$out"; then
        return 0
    fi
    if grep -qE "No public key|Can't check signature" <<<"$out"; then
        # Mozilla rotates its signing key, so take the key id from gpg itself.
        key=$(grep -oP 'using \S+ key \K[0-9A-F]+' <<<"$out" | head -1)
        warn "Mozilla signing key ${key:-(unknown)} is not in the keyring."
        warn "Import it with: gpg --recv-keys ${key:-<key-id>}"
        return 2
    fi
    return 1
}

# Fallback when the signature cannot be checked: compare the local size with
# the Content-Length the archive reports.
matches_remote_size() {
    local remote local_size
    remote=$(curl -sfIL "$SOURCE_URL/$NEW_TARBALL" \
        | grep -i '^content-length:' | tail -1 | tr -dc '0-9')
    [ -n "$remote" ] || return 2
    local_size=$(stat -c%s "$NEW_TARBALL" 2>/dev/null)
    [ "$remote" = "$local_size" ]
}

if ! skip_step 6; then
    step 6 "Downloading $NEW_TARBALL"

    # The detached signature is tiny - fetch it first so an already present
    # tarball can be checked without downloading the ~600 MB file again.
    rm -f "$NEW_TARBALL.asc"
    wget -q -O "$NEW_TARBALL.asc" "$SOURCE_URL/$NEW_TARBALL.asc" \
        || warn "No detached signature at $SOURCE_URL/$NEW_TARBALL.asc"

    NEED_DOWNLOAD=1
    if [ -f "$NEW_TARBALL" ]; then
        info "$NEW_TARBALL is already here, checking it against $NEW_TARBALL.asc"
        verify_tarball_signature
        case $? in
            0)  ok "Signature is good - reusing the local $NEW_TARBALL."
                NEED_DOWNLOAD=0 ;;
            1)  warn "Signature does NOT match - the local tarball is stale or corrupt."
                rm -f "$NEW_TARBALL" ;;
            2)  if matches_remote_size; then
                    warn "Falling back to a size check: local size matches the archive."
                    ok "Reusing the local $NEW_TARBALL."
                    NEED_DOWNLOAD=0
                else
                    info "Size differs from the archive (or is unknown) - downloading again."
                    rm -f "$NEW_TARBALL"
                fi ;;
        esac
        if [ "$NEED_DOWNLOAD" -eq 1 ] && [ -f sources ] \
           && grep -q "($NEW_TARBALL)" sources; then
            info "Removing the stale $NEW_TARBALL entry from sources"
            sed -i "\|($NEW_TARBALL)|d" sources
        fi
    fi

    if [ "$NEED_DOWNLOAD" -eq 1 ]; then
        run wget --progress=dot:giga -O "$NEW_TARBALL" "$SOURCE_URL/$NEW_TARBALL" \
            || { rm -f "$NEW_TARBALL"; die "Download of $SOURCE_URL/$NEW_TARBALL failed"; }
        ok "Downloaded $NEW_TARBALL ($(du -h "$NEW_TARBALL" | cut -f1))."
        verify_tarball_signature
        case $? in
            0) ok "PGP signature verified." ;;
            1) rm -f "$NEW_TARBALL" "$NEW_TARBALL.asc"
               die "Downloaded $NEW_TARBALL does not match its PGP signature" ;;
        esac
    fi

    rm -f "$NEW_TARBALL.asc"
fi

[ -f "$NEW_TARBALL" ] || die "$NEW_TARBALL is missing - re-run from step 6"

#-----------------------------------------------------------------------------
# Step 7: Download langpacks
#-----------------------------------------------------------------------------

if ! skip_step 7; then
    step 7 "Downloading langpacks"

    # The langpack tarball is named firefox-langpacks-<version>-<YYYYMMDD>.tar.xz.
    # If one for this version is already here, reuse it instead of downloading
    # every XPI again; the newest generation date wins.
    LANGPACK_FILE=$(ls -1 firefox-langpacks-"$NEW_VERSION"-*.tar.xz 2>/dev/null \
        | sort -V | tail -1)

    if [ -n "$LANGPACK_FILE" ]; then
        langpack_date="${LANGPACK_FILE##*-}"; langpack_date="${langpack_date%.tar.xz}"
        info "Langpack tarball for $NEW_VERSION already present, generated $langpack_date"
        info "Reusing $LANGPACK_FILE - delete it to force a fresh download."
    else
        [ -x ./moz-grab-langpacks ] || die "./moz-grab-langpacks not found or not executable"
        run ./moz-grab-langpacks -a firefox "$NEW_VERSION" \
            -u "$BUILD_URL/linux-x86_64/xpi/" \
            || die "moz-grab-langpacks failed"

        LANGPACK_FILE=$(ls -1 firefox-langpacks-"$NEW_VERSION"-*.tar.xz 2>/dev/null \
            | sort -V | tail -1)
        [ -n "$LANGPACK_FILE" ] || die "No firefox-langpacks-$NEW_VERSION-*.tar.xz was created"
        info "Langpack tarball: $LANGPACK_FILE"
    fi

    # Source1 keeps the %{version}%{?pre_version} macros, only the date changes.
    old_source1=$(spec_get '^Source1:\s*\K\S+')
    langpack_date="${LANGPACK_FILE##*-}"; langpack_date="${langpack_date%.tar.xz}"
    new_source1="firefox-langpacks-%{version}%{?pre_version}-$langpack_date.tar.xz"
    if [ "$old_source1" != "$new_source1" ]; then
        sed -i -E "s|^Source1:([[:space:]]*).*|Source1:\1$new_source1|" firefox.spec \
            || die "Cannot update Source1 in firefox.spec"
        info "Source1: $old_source1 -> $new_source1"
    fi
    ok "Using $LANGPACK_FILE; Source1 is up to date."
fi

if [ -z "$LANGPACK_FILE" ]; then
    LANGPACK_FILE=$(ls -1 firefox-langpacks-"$NEW_VERSION"-*.tar.xz 2>/dev/null \
        | sort -V | tail -1)
fi
[ -n "$LANGPACK_FILE" ] || die "No langpack tarball for $NEW_VERSION - re-run from step 7"

#-----------------------------------------------------------------------------
# Step 8: Upload new sources
#-----------------------------------------------------------------------------

if ! skip_step 8; then
    step 8 "Uploading new sources to the lookaside cache"
    [ "$DO_UPLOAD" -eq 1 ] && check_kerberos
    [ -f sources ] || die "No sources file in $PACKAGE_DIR"

    # Everything except the Firefox source/langpack tarballs is kept as is.
    mapfile -t KEPT_SOURCES < <(
        sed -nE 's|^[A-Za-z0-9]+ \(([^)]+)\).*|\1|p' sources \
            | grep -vE '^firefox-.*\.source\.tar\.xz$' \
            | grep -vE '^firefox-langpacks-.*\.tar\.xz$'
    )
    info "Kept sources:    ${KEPT_SOURCES[*]:-(none)}"
    info "Uploaded anew:   $NEW_TARBALL $LANGPACK_FILE"

    if [ "$DO_UPLOAD" -eq 0 ]; then
        warn "--no-upload: not uploading; updating the sources file locally only."
        # Same format as fedpkg: 'SHA512 (file) = hash'.
        grep -vE '\(firefox-.*\.source\.tar\.xz\)|\(firefox-langpacks-.*\.tar\.xz\)' \
            sources > sources.new
        sha512sum --tag "$NEW_TARBALL" "$LANGPACK_FILE" >> sources.new \
            || { rm -f sources.new; die "sha512sum failed"; }
        mv -f sources.new sources || die "Cannot replace the sources file"
        ok "sources now lists $NEW_TARBALL and $LANGPACK_FILE (not uploaded)."
        info "Someone with upload permission must still run in $PACKAGE_DIR:"
        info "  fedpkg new-sources $NEW_TARBALL $LANGPACK_FILE ${KEPT_SOURCES[*]}"
        UPLOAD_SKIPPED=1
    else
    # Trim the sources file first so that 'fedpkg sources' does not re-download
    # the previous (huge) Firefox tarball, then fetch whatever is still missing.
    cp sources sources.bak || die "Cannot back up the sources file"
    trap 'if [ -f "$PACKAGE_DIR/sources.bak" ]; then mv -f "$PACKAGE_DIR/sources.bak" "$PACKAGE_DIR/sources"; fi' EXIT
    grep -vE '\(firefox-.*\.source\.tar\.xz\)|\(firefox-langpacks-.*\.tar\.xz\)' \
        sources.bak > sources
    run fedpkg sources || die "fedpkg sources failed (Kerberos ticket expired?)"

    for f in "${KEPT_SOURCES[@]}"; do
        [ -f "$f" ] || die "Kept source $f is missing locally - cannot re-upload it"
    done

    run fedpkg new-sources "$NEW_TARBALL" "$LANGPACK_FILE" "${KEPT_SOURCES[@]}" \
        || die "fedpkg new-sources failed"

    trap - EXIT
    rm -f sources.bak
    ok "Uploaded $NEW_TARBALL and $LANGPACK_FILE; sources file refreshed."
    fi
fi

#-----------------------------------------------------------------------------
# Step 9: Check and rebase patches
#-----------------------------------------------------------------------------

if { [ "${#DROP_PATCHES[@]}" -gt 0 ] || [ "${#ADD_PATCHES[@]}" -gt 0 ]; } && skip_step 9; then
    warn "--drop-patch/--add-patch ignored: resuming at step $RESUME_FROM, past the patch step."
fi

if ! skip_step 9; then
    step 9 "Checking patches against the new sources"

    for p in "${DROP_PATCHES[@]}"; do
        drop_patch "$p"
    done
    [ "${#DROPPED_PATCHES[@]}" -gt 0 ] \
        && ok "Dropped ${#DROPPED_PATCHES[@]} patch(es)."

    for p in "${ADD_PATCHES[@]}"; do
        add_patch "$p"
    done
    [ "${#ADDED_PATCHES[@]}" -gt 0 ] \
        && ok "Added ${#ADDED_PATCHES[@]} patch(es)."

    mapfile -t SPEC_PATCHES < <(grep -oP '^Patch[0-9]*:\s*\K\S+' firefox.spec)
    info "${#SPEC_PATCHES[@]} patches referenced by firefox.spec"
    for p in "${SPEC_PATCHES[@]}"; do
        case "$p" in
            http*|%*) continue ;;
        esac
        [ -f "$p" ] || warn "Patch file referenced but missing: $p"
    done
    info "Patch application itself is verified by 'fedpkg prep' in the next step."
    ok "Patch list checked."
fi

#-----------------------------------------------------------------------------
# Step 10: Verify patches apply with fedpkg prep
#-----------------------------------------------------------------------------

if ! skip_step 10; then
    step 10 "Verifying patches with fedpkg prep"
    PREP_LOG=$(mktemp -t firefox-prep-XXXXXX.log)
    if run fedpkg prep 2>&1 | tee "$PREP_LOG"; then
        PREP_OK=1
    else
        PREP_OK=0
    fi
    if [ "$PREP_OK" -eq 0 ]; then
        printf '\n%sfedpkg prep failed. Failing patch(es):%s\n' "$C_RED" "$C_OFF" >&2
        grep -iE 'patch .*(FAILED|does not apply)|Hunk #.* FAILED|error:' "$PREP_LOG" \
            | tail -20 >&2
        printf '%sFull log: %s%s\n' "$C_YELLOW" "$PREP_LOG" "$C_OFF" >&2
        die "Rebase or drop the failing patch, then re-run: $0 $NEW_VERSION --resume 10"
    fi
    rm -f "$PREP_LOG"
    # The unpacked tree is kept for step 11 (NSS/NSPR version detection).
    ok "All patches apply cleanly."
    BUILD_STATUS="PASSED (fedpkg prep)"
fi
BUILD_STATUS="${BUILD_STATUS:-Not tested}"

#-----------------------------------------------------------------------------
# Step 11: Detect the NSS/NSPR versions shipped in the tarball
#
# Firefox bundles both sources; the versions are always taken from there and
# written to the spec, never asked for:
#   security/nss/lib/nss/nss.h    #define NSS_VERSION "3.127" _NSS_CUSTOMIZED
#   nsprpub/pr/include/prinit.h   #define PR_VERSION  "4.40"
#-----------------------------------------------------------------------------

DETECTED_NSS_VERSION=""
DETECTED_NSPR_VERSION=""

# read_bundled_version <relative-header> <define-name>
# Reads from the unpacked tree, falling back to the tarball when resuming.
read_bundled_version() {
    local header="$1" define="$2" path="firefox-$NEW_VERSION-build/$1"
    if [ -f "$path" ]; then
        grep -m1 -oP "^#define\s+$define\s+\"\K[^\"]+" "$path"
    else
        tar -xf "$NEW_TARBALL" --wildcards -O "*/$header" 2>/dev/null \
            | grep -m1 -oP "^#define\s+$define\s+\"\K[^\"]+"
    fi
}

# write_spec_version <macro> <old> <new> <label>
write_spec_version() {
    local macro="$1" old="$2" new="$3" label="$4"
    if [ "$old" = "$new" ]; then
        info "$macro: $new (unchanged)"
        return 0
    fi
    sed -i -E "s|^%global([[:space:]]+)$macro[[:space:]]+.*|%global\1$macro $new|" \
        firefox.spec || die "Cannot update $macro in firefox.spec"
    grep -qE "^%global[[:space:]]+$macro[[:space:]]+$(sed 's/[.[\*^$]/\\&/g' <<<"$new")\$" \
        firefox.spec || die "$macro was not updated in firefox.spec"
    SPEC_NOTES+=("$label requirement $old -> $new (detected in the tarball)")
    info "$macro: $old -> $new"
}

if ! skip_step 11; then
    step 11 "Detecting the NSS/NSPR versions from the Firefox sources"

    if [ ! -d "firefox-$NEW_VERSION-build" ]; then
        info "No unpacked tree - reading the headers from $NEW_TARBALL (this takes a while)"
    fi

    DETECTED_NSS_VERSION=$(read_bundled_version \
        "security/nss/lib/nss/nss.h" "NSS_VERSION")
    [ -n "$DETECTED_NSS_VERSION" ] \
        || die "Cannot read NSS_VERSION from security/nss/lib/nss/nss.h"

    DETECTED_NSPR_VERSION=$(read_bundled_version \
        "nsprpub/pr/include/prinit.h" "PR_VERSION")
    [ -n "$DETECTED_NSPR_VERSION" ] \
        || die "Cannot read PR_VERSION from nsprpub/pr/include/prinit.h"

    # PR_VERSION may carry a suffix, e.g. "4.40 Beta" - keep the number only.
    DETECTED_NSPR_VERSION="${DETECTED_NSPR_VERSION%% *}"

    printf '\n%s   Firefox %s bundles NSS %s and NSPR %s%s\n\n' \
        "$C_BOLD" "$NEW_VERSION" "$DETECTED_NSS_VERSION" "$DETECTED_NSPR_VERSION" "$C_OFF"

    write_spec_version nss_version  "$OLD_NSS_VERSION"  "$DETECTED_NSS_VERSION"  NSS
    NSS_VERSION="$DETECTED_NSS_VERSION"

    ok "NSS/NSPR versions written to firefox.spec."
fi

#-----------------------------------------------------------------------------
# Step 12: Local build (optional)
#-----------------------------------------------------------------------------

if ! skip_step 12; then
    if [ "$DO_LOCAL_BUILD" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
        printf '\n'
        confirm "Run a local build with 'fedpkg local'? It typically takes 1-2 hours." \
            && DO_LOCAL_BUILD=1
    fi
    if [ "$DO_LOCAL_BUILD" -eq 1 ]; then
        step 12 "Running a local build"
        LOCAL_LOG=$(mktemp -t firefox-local-XXXXXX.log)
        if run fedpkg local 2>&1 | tee "$LOCAL_LOG"; then
            ok "Local build succeeded."
            BUILD_STATUS="PASSED (fedpkg local)"
            rm -f "$LOCAL_LOG"
        else
            printf '\n%sLocal build failed. Relevant output:%s\n' "$C_RED" "$C_OFF" >&2
            grep -iE 'error:|No package .* found|not found|Installed \(but unpackaged\)' \
                "$LOCAL_LOG" | tail -30 >&2
            printf '%sFull log: %s%s\n' "$C_YELLOW" "$LOCAL_LOG" "$C_OFF" >&2
            cat >&2 <<'EOF'

Typical causes:
  * Missing BuildRequires  - add "BuildRequires: <pkg>-devel" to firefox.spec
  * Compile/linker error   - the source needs a patch for the new upstream API
  * Unpackaged files       - adjust the %files section of firefox.spec

EOF
            die "Fix the build, then re-run: $0 $NEW_VERSION --resume 12"
        fi
    else
        info "Skipping the local build."
    fi
fi

#-----------------------------------------------------------------------------
# Step 13: Commit the update
#-----------------------------------------------------------------------------

if ! skip_step 13; then
    step 13 "Committing the update"
    run git add firefox.spec sources || die "git add failed"

    # Patch files touched by hand (rebased/dropped) are staged too, but never
    # build artifacts.
    # Untracked files are ignored, and so are deletions: 'git rm' (used for
    # dropped patches) has already staged those, and 'git add' would fail on
    # a path that no longer exists.
    mapfile -t CHANGED_PATCHES < <(git status --porcelain --untracked-files=no \
        -- '*.patch' '*.diff' | awk '$1 !~ /D/ {print $NF}')
    if [ "${#CHANGED_PATCHES[@]}" -gt 0 ]; then
        info "Modified patch files: ${CHANGED_PATCHES[*]}"
        if confirm "Stage these patch files as part of the update?" y; then
            run git add -A -- "${CHANGED_PATCHES[@]}" || die "git add of patches failed"
        fi
    fi

    printf '\n%sStaged changes:%s\n' "$C_BOLD" "$C_OFF"
    git status --short --untracked-files=no

    show_staged_diff
    confirm "Commit these changes?" y || die "Commit cancelled - the changes stay staged"

    run fedpkg commit -c || die "fedpkg commit failed"
    ok "Committed: $(git log -1 --pretty=%s)"
fi

#-----------------------------------------------------------------------------
# Step 14: Present summary and push
#-----------------------------------------------------------------------------

step 14 "Update summary"

cat <<EOF

${C_BOLD}Firefox Update Summary: $OLD_VERSION -> $NEW_VERSION${C_OFF}

  Version:       $OLD_VERSION -> $NEW_VERSION
  Branch:        rawhide
  Mozilla build: $BUILD_VERSION
  Build status:  $BUILD_STATUS

  Sources:
    - $NEW_TARBALL
    - $LANGPACK_FILE
EOF

if [ -n "$DETECTED_NSS_VERSION$DETECTED_NSPR_VERSION" ]; then
    echo
    echo "  NSS/NSPR (detected in the Firefox sources):"
    echo "    - NSS:  $OLD_NSS_VERSION -> $DETECTED_NSS_VERSION"
    echo "    - NSPR: $OLD_NSPR_VERSION -> $DETECTED_NSPR_VERSION"
fi

if [ "${#DROPPED_PATCHES[@]}" -gt 0 ]; then
    echo
    echo "  Dropped patches:"
    printf '    - %s\n' "${DROPPED_PATCHES[@]}"
fi

if [ "${#SPEC_NOTES[@]}" -gt 0 ]; then
    echo
    echo "  SPEC changes:"
    printf '    - %s\n' "${SPEC_NOTES[@]}"
fi

echo
echo "  Commit:"
git log -1 --pretty='    %h %s'
echo

if [ "${UPLOAD_SKIPPED:-0}" -eq 1 ]; then
    warn "Sources were NOT uploaded (--no-upload): do not push until the"
    warn "tarballs are in the lookaside cache (someone with permission can run"
    warn "'fedpkg new-sources', or upload them by other means)."
fi

if [ "$DO_PUSH" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
    confirm "Push the commit to rawhide on Fedora dist-git?" && DO_PUSH=1
fi

if [ "$DO_PUSH" -eq 1 ]; then
    check_kerberos
    run fedpkg push || die "fedpkg push failed"
    ok "Pushed to Fedora dist-git (rawhide)."
    info "Start a build with: fedpkg build"
else
    ok "Update prepared but not pushed. Push later with: fedpkg push"
fi
