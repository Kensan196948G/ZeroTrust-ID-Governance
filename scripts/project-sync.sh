#!/bin/bash
# ===================================
# project-sync.sh
# GitHub Project ステータス同期スクリプト
# ClaudeOS Orchestrator から呼び出されます
# ===================================

set -euo pipefail

ISSUE_NUMBER="${1:-}"
STATUS="${2:-}"
REPO="Kensan196948G/ZeroTrust-ID-Governance"
PROJECT_NUMBER=12

if [[ -z "$ISSUE_NUMBER" || -z "$STATUS" ]]; then
  echo "Usage: $0 <issue_number> <status>"
  echo "Status: Inbox|Backlog|Ready|Design|Development|Verify|Deploy Gate|Done|Blocked"
  exit 1
fi

# Issue を Project に追加（既存の場合はスキップ）
ISSUE_URL="https://github.com/${REPO}/issues/${ISSUE_NUMBER}"
gh project item-add "$PROJECT_NUMBER" --owner Kensan196948G --url "$ISSUE_URL" 2>/dev/null || true

# Project の Status フィールド ID を取得
FIELD_ID=$(gh project field-list "$PROJECT_NUMBER" --owner Kensan196948G --format json \
  | jq -r '.fields[] | select(.name == "Status") | .id' 2>/dev/null || echo "")

if [[ -z "$FIELD_ID" ]]; then
  echo "Warning: Status field not found in project. Using label as fallback."
  gh issue edit "$ISSUE_NUMBER" --repo "$REPO" --add-label "status:${STATUS,,}" 2>/dev/null || true
  echo "Issue #$ISSUE_NUMBER status updated to: $STATUS (via label)"
  exit 0
fi

# Item ID を取得
ITEM_ID=$(gh project item-list "$PROJECT_NUMBER" --owner Kensan196948G --format json \
  | jq -r --arg url "$ISSUE_URL" '.items[] | select(.content.url == $url) | .id' 2>/dev/null || echo "")

if [[ -z "$ITEM_ID" ]]; then
  echo "Warning: Item not found in project for issue #$ISSUE_NUMBER"
  exit 1
fi

# Status オプション ID を取得
OPTION_ID=$(gh project field-list "$PROJECT_NUMBER" --owner Kensan196948G --format json \
  | jq -r --arg status "$STATUS" \
    '.fields[] | select(.name == "Status") | .options[] | select(.name == $status) | .id' \
  2>/dev/null || echo "")

if [[ -z "$OPTION_ID" ]]; then
  echo "Warning: Status option '$STATUS' not found. Available: Inbox, Backlog, Ready, Design, Development, Verify, Deploy Gate, Done, Blocked"
  exit 1
fi

# GraphQL でステータス更新
gh api graphql -f query='
  mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $project
      itemId: $item
      fieldId: $field
      value: { singleSelectOptionId: $value }
    }) {
      projectV2Item { id }
    }
  }' \
  -f project="PVT_kwHOClgkIc4BSuPD" \
  -f item="$ITEM_ID" \
  -f field="$FIELD_ID" \
  -f value="$OPTION_ID"

echo "Issue #$ISSUE_NUMBER status updated to: $STATUS"
