#!/usr/bin/env python3
"""按保留天数清理本仓库的 Actions 运行记录。

GitHub 默认保留 90 天运行记录，日更工作流很快就会堆出上百条无用历史。
本脚本把保留期收紧到 keep_days（默认 7 天），同时给每个工作流保底保留
keep_recent 条，避免第一次运行就把历史清空。

环境变量：
    GH_TOKEN        必填，仓库密钥 ACTION_TOKEN / GH_TOKEN，或工作流内置 GITHUB_TOKEN
    WORKFLOWS       必填，逗号分隔的工作流文件名
    KEEP_DAYS       保留天数，默认 7
    KEEP_RECENT     每个工作流最少保留条数，默认 3
    DRY_RUN         true 时只列出待删除记录，默认 false
    GITHUB_REPOSITORY / GITHUB_RUN_ID 由 Actions 自动注入
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get('GITHUB_API_URL', 'https://api.github.com').rstrip('/')
REPO = os.environ['GITHUB_REPOSITORY']
SELF_RUN = int(os.environ.get('GITHUB_RUN_ID', '0') or 0)
TOKEN = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
HEADERS = {
    'Authorization': 'Bearer ' + TOKEN,
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'ros-cnip-rsc-clean-workflows',
}


def call(method: str, url: str):
    """发起一次 API 调用，返回 (status, payload)。"""
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')


def stamp(run: dict, field: str, fallback: datetime.datetime) -> datetime.datetime:
    """解析运行记录里的时间戳（UTC）。

    注意用 created_at 而不是 updated_at 判断新旧：GitHub 会因日志过期等内部
    操作刷新 updated_at，几个月前的记录也可能显示「刚刚更新」。
    """
    value = run.get(field) or run.get('created_at') or ''
    if not value:
        return fallback
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))


def fetch_runs(workflow: str, failures) -> list:
    """分页拉取某个工作流的全部运行记录。

    这个接口不返回 total_pages，只能按 total_count 判断是否取完；
    MAX_PAGES 只是防止接口异常时死循环。
    """
    runs, page, max_pages = [], 1, 50
    while True:
        status, data = call(
            'GET',
            f'{API}/repos/{REPO}/actions/workflows/{workflow}/runs'
            f'?per_page=100&page={page}',
        )
        if status != 200:
            failures.append(f'{workflow}: 列表失败 HTTP {status} {data}')
            return runs
        items = data.get('workflow_runs', [])
        runs += items
        if not items or len(runs) >= data.get('total_count', len(runs)) or page >= max_pages:
            return runs
        page += 1


def select(runs, cutoff, keep_recent, now):
    """返回 (保留列表, 待删除列表)。按新旧排序后先算保留期，再补足保底条数。"""
    fresh, stale = [], []
    for run in runs:
        # 进行中的运行不算「旧记录」，也不该被删除（包括本工作流自己）。
        if run['status'] != 'completed' or run['id'] == SELF_RUN:
            fresh.append(run)
        elif stamp(run, 'created_at', now) >= cutoff:
            fresh.append(run)
        else:
            stale.append(run)
    stale.sort(key=lambda r: stamp(r, 'created_at', now), reverse=True)
    reserve = max(0, keep_recent - len(fresh))
    return fresh, stale[reserve:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep-days', type=int,
                        default=int(os.environ.get('KEEP_DAYS') or 7))
    parser.add_argument('--keep-recent', type=int,
                        default=int(os.environ.get('KEEP_RECENT') or 3))
    parser.add_argument('--dry-run', action='store_true',
                        default=(os.environ.get('DRY_RUN', '').strip().lower()
                                 in ('1', 'true', 'yes', 'on')))
    parser.add_argument('--workflows', default=os.environ.get('WORKFLOWS', ''))
    args = parser.parse_args()

    workflows = [w.strip() for w in args.workflows.split(',') if w.strip()]
    if not workflows:
        print('::error::WORKFLOWS 为空')
        return 1
    if not TOKEN:
        print('::error::缺少 GH_TOKEN')
        return 1

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=args.keep_days)
    failures, removed = [], 0

    print(f'保留策略：{args.keep_days} 天（早于 {cutoff:%Y-%m-%d %H:%M} UTC 的记录会被删除），'
          f'每个工作流最少 {args.keep_recent} 条'
          + ('；dry-run，不实际删除' if args.dry_run else ''))

    for workflow in workflows:
        runs = fetch_runs(workflow, failures)
        runs.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        fresh, doomed = select(runs, cutoff, args.keep_recent, now)
        print(f'::group::{workflow}: 共 {len(runs)} 条，保留 {len(fresh)} 条，'
              f'{"待删除" if args.dry_run else "删除"} {len(doomed)} 条')
        for run in doomed:
            age = (now - stamp(run, 'created_at', now)).days
            info = (f'{run["id"]} {stamp(run, "created_at", now):%Y-%m-%d} '
                    f'({age} 天前) {run["conclusion"]}')
            if args.dry_run:
                print(f'  {info}')
                continue
            status, body = call('DELETE', f'{API}/repos/{REPO}/actions/runs/{run["id"]}')
            if status in (202, 204):
                removed += 1
            else:
                failures.append(f'{info} 删除失败 HTTP {status} {body}')
                if status in (403, 429):
                    failures.append('接口限流或权限不足，跳过剩余记录')
                    break
                time.sleep(0.1)
        print('::endgroup::')

    for message in failures:
        print(f'::warning::{message}')
    if args.dry_run:
        print('dry-run 结束，没有删除任何记录')
    else:
        print(f'完成，删除 {removed} 条运行记录')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
