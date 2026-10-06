# -*- coding: utf-8 -*-
"""Pachisi 十字戏：贝壳棋盘。纯标准库。"""
from __future__ import annotations
import argparse
import copy
import random
import sys

TRACK = 68            # 外圈格数
SAFE = {0, 8, 13, 21, 26, 34, 39, 47, 52, 60, 65}  # 安全格
STARTS = {0: 0, 1: 17, 2: 34, 3: 51}  # 各家起点
HOME_RUN = 6          # 终点道长度
GRACE = (6, 10, 25)   # 贝壳特殊值：进场/加回合/1步
ROLL_MAX = 25

class IllegalMove(Exception):
    pass

class Pachisi:
    """四人制，简化规则。位置：-1=营中, 0..67=赛道, 100..105=终点道, 200=到家。"""

    def __init__(self, players: int = 4, seed: int | None = None):
        if players not in (2, 4):
            raise ValueError("只支持 2 或 4 人")
        self.players = players
        self.rng = random.Random(seed)
        self.pos = {p: [-1, -1, -1, -1] for p in range(players)}
        self.turn = 0

    # -- 贝壳 --
    def throw(self) -> int:
        """简化：7 颗贝壳，正面数加权，0 全反=25。"""
        up = sum(1 for _ in range(7) if self.rng.random() < 0.5)
        return {0: 6, 7: 12}.get(up, up) if up != 0 else 25

    # -- 位置工具 --
    def abs_pos(self, player: int, steps: int) -> int:
        return (STARTS[player] + steps) % TRACK

    def home_pos(self, player: int, steps: int) -> int:
        """steps: 已走步数。终点道入口在 steps == 51 处。"""
        return 100 + (steps - 51) if steps >= 51 else self.abs_pos(player, steps)

    # -- 走法 --
    def legal_moves(self, player: int, roll: int) -> list[tuple[int, str, int]]:
        """返回 (棋子索引, 动作, 目标steps)。动作: enter / move / home。"""
        out = []
        for i, st in enumerate(self.pos[player]):
            if st == -1:
                if roll in GRACE:  # 6/10/25 可进场
                    out.append((i, "enter", 0))
                continue
            if st == 200:
                continue
            ns = st + roll
            if ns > 51 + HOME_RUN:
                continue  # 到家需精确步数
            if ns == 51 + HOME_RUN:
                out.append((i, "home", ns))
            else:
                out.append((i, "move", ns))
        return out

    def apply(self, player: int, move: tuple[int, str, int], roll: int) -> dict:
        if move not in self.legal_moves(player, roll):
            raise IllegalMove(f"非法走法: {move}")
        i, act, target = move
        info = {"captured": [], "extra": False}
        if act == "enter":
            self.pos[player][i] = 0
            info["extra"] = True
        elif act == "home":
            self.pos[player][i] = 200
            info["extra"] = True
        else:
            self.pos[player][i] = target
            apos = self.abs_pos(player, target)
            if apos not in SAFE:
                for q in range(self.players):
                    if q == player:
                        continue
                    for j, qst in enumerate(self.pos[q]):
                        if qst not in (-1, 200) and qst < 51 and self.abs_pos(q, qst) == apos:
                            self.pos[q][j] = -1
                            info["captured"].append((q, j))
                if info["captured"]:
                    info["extra"] = True
        return info

    def finished(self, player: int) -> bool:
        return all(s == 200 for s in self.pos[player])

    # -- AI --
    def ai_choose(self, player: int, roll: int):
        moves = self.legal_moves(player, roll)
        if not moves:
            return None
        def key(m):
            i, act, t = m
            if act == "home":
                return (4, 0)
            if act == "enter":
                return (3, 0)
            # 模拟吃子
            apos = self.abs_pos(player, t)
            cap = 0
            if apos not in SAFE:
                for q in range(self.players):
                    if q == player:
                        continue
                    cap += sum(1 for qst in self.pos[q]
                               if qst not in (-1, 200) and qst < 51 and self.abs_pos(q, qst) == apos)
            # 危险度：落点后是否会被吃
            danger = 0
            if apos not in SAFE and t < 51:
                danger = sum(1 for q in range(self.players) if q != player
                             for qst in self.pos[q]
                             if qst not in (-1, 200) and qst < 51
                             and 1 <= (self.abs_pos(player, t) - self.abs_pos(q, qst)) % TRACK <= 12)
            return (2 + cap, t - danger)
        return max(moves, key=key)

    # -- 对局 --
    def play_game(self, verbose: bool = False) -> tuple[int, int]:
        """返回 (胜者, 掷次数)。"""
        throws = 0
        while throws < 2000:
            p = self.turn
            roll = self.throw()
            throws += 1
            mv = self.ai_choose(p, roll)
            extra = False
            if mv:
                info = self.apply(p, mv, roll)
                extra = info["extra"]
            if roll == 25:
                extra = True  # 25 加回合
            if self.finished(p):
                return p, throws
            if not extra:
                self.turn = (self.turn + 1) % self.players
        return -1, throws  # 和棋

    def board_text(self) -> str:
        lines = []
        for p in range(self.players):
            cells = []
            for s in self.pos[p]:
                cells.append("营" if s == -1 else ("家" if s == 200 else str(s)))
            lines.append(f"玩家{p}: {' '.join(cells)}")
        return "\n".join(lines)


def cmd_auto(args):
    wins = [0] * args.players
    draws = 0
    total = 0
    for g in range(args.games):
        game = Pachisi(players=args.players, seed=None if args.seed is None else args.seed + g)
        w, t = game.play_game()
        total += t
        if w < 0:
            draws += 1
        else:
            wins[w] += 1
        if args.verbose:
            print(f"第 {g+1}/{args.games} 局: {'和棋' if w < 0 else f'玩家{w}胜'} ({t} 掷)")
    print(f"总计: {args.games} 局, " + ", ".join(f"玩家{i}胜{wins[i]}" for i in range(args.players)) + f", 和棋{draws}")
    print(f"平均 {total / args.games:.1f} 掷/局")


def cmd_play(args):
    if not sys.stdin.isatty():
        print("交互模式需要终端；无头演示请用 --auto", file=sys.stderr)
        sys.exit(2)
    game = Pachisi(players=args.players, seed=args.seed)
    humans = {0}
    print("=== Pachisi 十字戏 ===")
    print("你是玩家 0。命令: <棋子号> 走子 / q 退出")
    while True:
        p = game.turn
        roll = game.throw()
        print(f"\n--- 玩家{p} 掷出 {roll} ---")
        print(game.board_text())
        moves = game.legal_moves(p, roll)
        if p in humans:
            if not moves:
                print("无棋可走。")
                extra = False
            else:
                print("可选:", {i: f"{act}->{t}" for i, act, t in moves})
                while True:
                    s = input("走哪颗? ").strip()
                    if s == "q":
                        return
                    try:
                        idx = int(s)
                    except ValueError:
                        continue
                    cand = [m for m in moves if m[0] == idx]
                    if cand:
                        info = game.apply(p, cand[0], roll)
                        extra = info["extra"]
                        break
                    print("非法, 重选。")
        else:
            mv = game.ai_choose(p, roll)
            if mv:
                info = game.apply(p, mv, roll)
                extra = info["extra"]
                print(f"AI 走 {mv}")
            else:
                print("AI 无棋可走。")
                extra = False
        if roll == 25:
            extra = True
        if game.finished(p):
            print(f"\n*** 玩家{p} 获胜! ***")
            return
        if not extra:
            game.turn = (game.turn + 1) % game.players


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pachisi 十字戏（贝壳棋盘）")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--players", type=int, default=4, choices=[2, 4])
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.auto:
        cmd_auto(args)
    else:
        cmd_play(args)


if __name__ == "__main__":
    main()
