#!/usr/bin/env bash
# GitHub Actions 日志分组助手；本地运行时为空操作。
# 用法：gha_group "标题" ... gha_endgroup

gha_group() {
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    printf '::group::%s\n' "$*"
  fi
  return 0
}

gha_endgroup() {
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    printf '::endgroup::\n'
  fi
  return 0
}
