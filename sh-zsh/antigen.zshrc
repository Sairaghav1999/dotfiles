## Bundles
antigen_default_bundles=()
antigen_default_bundles+='git'
antigen_default_bundles+='pip'
antigen_default_bundles+='command-not-found'

antigen_third_party_bundles=()
antigen_third_party_bundles+='Tarrasch/zsh-autoenv'
antigen_third_party_bundles+='zsh-users/zsh-syntax-highlighting'  # Keep last

## Theme
# antigen_theme_name="agnoster"
# antigen_theme_repo="https://gist.github.com/3750104.git"

## Extra configuration variables
# How often to auto-update (in days).
UPDATE_ZSH_DAYS=1
# Command auto-correction.
ENABLE_CORRECTION="true"
# display red dots whilst waiting for completion.
COMPLETION_WAITING_DOTS="true"

_overlap_log "Sourcing antigen.zsh"
source ~/.sh-zsh/antigen/antigen.zsh

_overlap_log "Enabling oh-my-zsh..."
antigen use oh-my-zsh

# Default bundles
for bundle in $antigen_default_bundles; do
    _overlap_log "Enabling default oh-my-zsh bundles: ${bundle}"
    antigen bundle $bundle
done

# Third party bundles
for bundle in $antigen_third_party_bundles; do
    _overlap_log "Enabling third-party oh-my-zsh bundles: ${bundle}"
    antigen bundle $bundle
done

if [[ ! -z $antigen_theme_name ]]; then
    # Load the theme.
    _overlap_log "Loading oh-my-zsh theme... "
    antigen theme $antigen_theme_repo $antigen_theme_name
fi

# Tell antigen that you're done.
_overlap_log "Applying Changes..."
antigen apply

# Clear out!
_overlap_log
