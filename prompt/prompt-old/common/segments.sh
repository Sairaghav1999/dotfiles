# -----------------------------------------------------------------------------
# Git
# -----------------------------------------------------------------------------
_prompt_segment_git() {
    # Verify that we have git
    command -v git >/dev/null 2>&1 || return

    # Only add information if we are in a repository
    git rev-parse --is-inside-work-tree > /dev/null 2>&1 || return

    # HEAD related information
    git_HEAD_ref=$(git symbolic-ref HEAD 2> /dev/null)
    if [[ $git_HEAD_ref == "refs/heads/"* ]]; then
        git_head_status="$(_prompt_git_branch_upstream_info)"
    else
        git_head_status="$(_prompt_git_detached_HEAD_info)"
    fi

    # Working Directory information
    git_segment_text="$git_head_status"
    git_working_dir_status="$(_prompt_git_working_dir_info)"
    if [[ -n $git_working_dir_status ]]; then
        git_segment_text+="$git_working_dir_status"
    fi
    # Return the text for the git segments
    _prompt_write "$git_segment_text"
}

_prompt_git_working_dir_info() {
    deleted=$(git ls-files -d | wc -l)
    modified=$(git ls-files -m | wc -l)
    unmerged=$(git ls-files -u | wc -l)
    untracked=$(git ls-files -o --exclude-standard | wc -l)
    staged=$(git diff --cached --numstat | wc -l)

    if (( ${staged} > 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_staged_file)
        _prompt_write "${staged}${_PROMPT_SYMBOLS[git_staged_file]} "
    fi
    if (( ${untracked} > 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_untracked_file)
        _prompt_write "${untracked}${_PROMPT_SYMBOLS[git_untracked_file]} "
    fi
    if (( ${unmerged} > 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_unmerged_file)
        _prompt_write "${unmerged}${_PROMPT_SYMBOLS[git_unmerged_file]} "
    fi
    if (( ${modified} > 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_modified_file)
        _prompt_write "${modified}${_PROMPT_SYMBOLS[git_modified_file]} "
    fi
    if (( ${deleted} > 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_deleted_file)
        _prompt_write "${deleted}${_PROMPT_SYMBOLS[git_deleted_file]} "
    fi
    if (( ${deleted} + ${modified} + ${unmerged} + ${untracked} + ${staged} == 0 )); then
        _prompt_color_fg_start $(_prompt_segment_fg git_repo_clean)
        _prompt_write "${_PROMPT_SYMBOLS[git_repo_clean]} "
    fi
}

_prompt_git_detached_HEAD_info() {
    # Get the commit hash
    git_hash="$(git rev-parse --short=20 HEAD)"
    # Return the hash
    _prompt_color_fg_start $(_prompt_segment_fg git_hash)
    _prompt_write " ${_PROMPT_SYMBOLS[git_hash_prefix]}$git_hash "
}

_prompt_git_branch_upstream_info() {
    # Get branch name, upstream name
    git_HEAD_ref="$(git symbolic-ref HEAD)"
    git_branch_name="${git_HEAD_ref:11}"

    git_upstream_name="$(git rev-parse --abbrev-ref "@{upstream}" 2>/dev/null)"

    # Figure out divergence information.
    if [[ $? == 0 ]]; then
        temp="$(git rev-list --count --left-right "$git_upstream_name...HEAD")"
        behind=$(echo -n $temp | cut -f1)
        ahead=$(echo -n $temp | cut -f2)
    fi

    ### Return the collected information, in a properly formatted manner.
    # Branch name
    _prompt_write " "
    _prompt_color_fg_start $(_prompt_segment_fg git_branch_name_prefix)
    _prompt_write "${_PROMPT_SYMBOLS[git_branch_name_prefix]} "
    _prompt_color_fg_start $(_prompt_segment_fg git_branch_name)
    _prompt_write "$git_branch_name"
    if [[ -n $git_upstream_name ]]; then
        _prompt_write " "
        # Upstream name
        _prompt_color_fg_start $(_prompt_segment_fg git_upstream_pointer)
        _prompt_write "${_PROMPT_SYMBOLS[git_upstream_pointer]} "
        _prompt_color_fg_start $(_prompt_segment_fg git_upstream_name)
        _prompt_write "$git_upstream_name"
        # Divergence text
        git_divergence=
        if (( ahead > 0 )); then
            git_divergence+=" $(_prompt_color_fg_start $(_prompt_segment_fg git_deviation_ahead))"
            git_divergence+=" ${_PROMPT_SYMBOLS[git_deviation_ahead]}$ahead"
        fi
        if (( behind > 0 )); then
            git_divergence+=" $(_prompt_color_fg_start $(_prompt_segment_fg git_deviation_behind))"
            git_divergence+=" ${_PROMPT_SYMBOLS[git_deviation_behind]}$behind"
        fi
        _prompt_write $git_divergence
    fi
    _prompt_write " "
}

# -----------------------------------------------------------------------------
# Python Virtual Environment
# -----------------------------------------------------------------------------
_prompt_segment_virtualenv() {
    venv_name=$(basename "$VIRTUAL_ENV")
    if [[ -n $venv_name ]]; then
        _prompt_color_fg_start $(_prompt_segment_fg virtualenv_name)
        _prompt_write " $venv_name "
    fi
}
# Because it just got integrated into the prompt!!
export VIRTUAL_ENV_DISABLE_PROMPT=1

# -----------------------------------------------------------------------------
# Ruby Version Manager
# -----------------------------------------------------------------------------
_prompt_segment_rvm() {
    rvm_text=$(rvm-prompt 2>/dev/null)
    if [[ -n $rvm_text ]]; then
        _prompt_color_fg_start $(_prompt_segment_fg rvm)
        _prompt_write " $rvm_text "
    fi
}

# -----------------------------------------------------------------------------
# Background Jobs
# -----------------------------------------------------------------------------
_prompt_segment_background_job_count() {
    job_count=$(jobs -r | wc -l)
    if [[ $job_count != '0' ]]; then
        _prompt_color_fg_start $(_prompt_segment_fg background_job_count)
        _prompt_write " ${_PROMPT_SYMBOLS[background_job_count]}$job_count "
    fi
}

# -----------------------------------------------------------------------------
# Working Directory
# -----------------------------------------------------------------------------
_prompt_working_dir_path_components() {
    # We go up the path. On reaching root, come out...
    while [[ "$PWD" != "/" ]]; do
        if [[ "$PWD" == "$HOME" ]]; then
            echo "~"
            return
        fi
        _file="$PWD/$DIRNAME_FILENAME"
        if [[ -f "${_file}" ]]; then
            echo "+${_file}"
            return
        else
            echo "-$(basename ${PWD})"
        fi
        builtin cd .. &>/dev/null
    done
}

_prompt_substituted_working_dir() {
    AUTOENV_DISABLED=1  # speed stuff up.
    defIFS=$IFS
    IFS=$(echo -en "\n\b")

    typeset __array_offset

    if [[ -n "${ZSH_VERSION}" ]]; then
        __array_offset=0
    else
        __array_offset=1
    fi

    typeset target home _file
    typeset -a _files

    # set -x
    _files=( $(_prompt_working_dir_path_components) )
    # set +x

    _file=${#_files[@]}
    while (( _file > 0 )); do
        envfile=${_files[_file-__array_offset]}
        # autoenv_check_authz_and_run "$envfile"
        if [[ ${envfile} == "~" ]]; then
            echo -n "~"
        elif [[ ${envfile} == +* ]]; then
            fname="$(echo "${envfile}" | cut -c2-)"
            echo -n "${_PROMPT_SYMBOLS[working_directory_aliased]}"
            cat $fname | tr -d "\n"
        elif [[ ${envfile} == -* ]]; then
            echo -n "${_PROMPT_SYMBOLS[working_directory_seperator]}"
            echo "${envfile}" | cut -c2- | tr -d "\n"
        fi
        : $(( _file -= 1 ))
    done

    IFS=$defIFS
    AUTOENV_DISABLED=0
}

_prompt_segment_working_directory() {
    # Allows for assigning a special name to directories.
    _prompt_color_fg_start $(_prompt_segment_fg working_directory)

    _prompt_write " $(_prompt_substituted_working_dir) "
}

# -----------------------------------------------------------------------------
# User Name
# -----------------------------------------------------------------------------
_prompt_segment_user_name() {
    if [[ ${USER} != ${DEFAULT_USER} ]]; then
        _prompt_color_fg_start $(_prompt_segment_fg user_name)
        _prompt_write " ${USER} "
    fi
}

_prompt_debug() {
    cd ~/code/projects/python/Py2C
    set -x
    _prompt_working_dir_path_components
    set +x
}