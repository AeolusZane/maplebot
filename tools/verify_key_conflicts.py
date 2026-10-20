"""Offline key-conflict rules; no game input or personal configuration writes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.ui.key_conflicts import conflicts

assert conflicts([('补血','Home'),('跳跃','HOME')])=={'home':['补血','跳跃']}
assert conflicts([('补血','Page Up'),('补血','pgup')])=={}
assert set(conflicts([('补血','END'),('补蓝','end')])['end'])=={'补血','补蓝'}
assert conflicts([('跳跃',''),('瞬移',None)])=={}
assert conflicts([('增益技能 1','F6'),('增益技能 2','f6')])=={'f6':['增益技能 1','增益技能 2']}
print('PASS: duplicate actions, potion tiers, aliases and empty keys')
