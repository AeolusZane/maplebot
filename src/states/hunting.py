from src.states.base_state import State

class HuntingState(State):
    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def check_transitions(self):
        # 国服怀旧服无符文系统，打怪状态不再需要转移到其它状态
        return None

    def on_frame(self):
        if getattr(self.bot, 'graph_navigator', None) is not None:
            import time
            from src.utils.logger import logger
            nav = self.bot.graph_navigator
            nav.input_latency_ms=getattr(self.bot,'_latency_ms',0)
            self.bot.monsters=[]
            now=time.monotonic()
            if hasattr(self.bot,'refresh_visible_monsters'):self.bot.refresh_visible_monsters(now)
            valid=getattr(self.bot,'graph_position_valid',False)
            escape=getattr(nav,'reset_escape',None)
            here=nav.locate(self.bot.loc_player_global) if hasattr(nav,'locate') and valid else None
            platform=getattr(nav,'platforms',{}).get(here,{})
            if escape is None and platform.get('reset_point'):
                from src.navigation.map_graph import shortest_path
                exits=[p for p in nav.platforms.values() if not p.get('reset_point') and shortest_path(nav.graph,here,p['id'])]
                if not exits:
                    from src.navigation.reset_escape import ResetEscape
                    escape=nav.reset_escape=ResetEscape(platform,nav.graph.get('ropes',[]),now)
                    nav.rope_recovery=None;nav.fault=None;nav.transit=None
            if escape is not None:
                command,status=escape.step(self.bot.loc_player_global,now,valid,bool(platform) and not platform.get('reset_point'))
                nav.status=status;nav.last_progress=now
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=command
                self.bot._combat_hold=False
                self.bot.kb.set_command(' '.join(command));self.bot.cmd_move_x_last=command[0]
                if status!=self.bot._graph_status_last:
                    logger.info('[复位点离开] '+status);self.bot._graph_status_last=status
                if escape.done:
                    nav.reset_escape=None;nav.path=[];nav.goal=None;nav.aim=None;nav.hunt_target=None
                    nav.current=here;nav.rope_recovery=None;nav.fault=None
                return
            if hasattr(nav,'release_failed_rope'):
                if nav.release_failed_rope(self.bot.loc_player_global,now,valid):
                    logger.info('[地图导航] '+nav.status)
            recovery=nav.recover_rope(self.bot.loc_player_global,now,valid) if hasattr(nav,'recover_rope') else None
            if getattr(nav,'fault',None) and hasattr(nav,'recover_fault'):
                recovery=nav.recover_fault(self.bot.loc_player_global,now,valid)
            startup=getattr(self.bot,'_startup_position',None)
            if recovery is None and startup is not None:
                grounded=valid and nav.locate(self.bot.loc_player_global) is not None
                recovery=startup.step(now,grounded and getattr(self.bot,'nametag_hit',False))
                if recovery is not None:nav.status='启动定位：左右移动＋短跳，确认平台定位后提前结束'
            if recovery is None and hasattr(nav,'recover_unknown'):
                recovery=nav.recover_unknown(self.bot.loc_player_global,now,valid)
            if recovery is not None:
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=recovery
                self.bot._combat_hold=False
                from src.states.combat_hold import CombatHold
                self.bot._combat_tracker=CombatHold();nav._combat_paused_at=None
                if getattr(nav,'horizontal_motion',None):nav.horizontal_motion.cancel()
                # During the observation pause only, reliable screen localization can
                # support combat even though the map's platform geometry is unmatched.
                if (recovery==('none','none','none') and getattr(nav,'_unknown_failed',None)
                        and now<getattr(nav,'_unknown_retry_at',0) and valid
                        and getattr(self.bot,'nametag_hit',False)
                        and not getattr(nav,'rope_recovery',None)
                        and not any(abs(self.bot.loc_player_global[0]-r['x'])<=2 and
                                    r['y1']<=self.bot.loc_player_global[1]<=r['y2']
                                    for r in getattr(nav,'graph',{}).get('ropes',[]))
                        and hasattr(self.bot,'update_cmd_by_mob_detection')):
                    self.bot.is_on_ladder=False
                    self.bot.update_cmd_by_mob_detection()
                    if self.bot.cmd_action=='attack':
                        recovery=(self.bot.cmd_move_x,'none','attack')
                        nav.status='未知平台观察期间：人物定位可靠，攻击范围内怪物；稍后继续恢复'
                self.bot.kb.set_command(' '.join(recovery));self.bot.cmd_move_x_last=recovery[0]
                if nav.status!=self.bot._graph_status_last:
                    logger.info('[地图导航] '+nav.status);self.bot._graph_status_last=nav.status
                return
            from src.states.combat_hold import LocalizationGate
            if not hasattr(nav,'localization_gate'):nav.localization_gate=LocalizationGate()
            # The screen anchor already retains the last successful nametag position.
            # Occlusion must not interrupt minimap-driven movement; never use the
            # initial screen coordinate before the first successful detection.
            has_reference=(getattr(self.bot,'nametag_hit',True) or
                           getattr(self.bot,'nametag_ever_hit',False))
            ready,paused=nav.localization_gate.update(valid and has_reference,now)
            if not ready:
                if getattr(nav,'horizontal_motion',None):nav.horizontal_motion.cancel()
                self.bot.cmd_move_x=self.bot.cmd_move_y=self.bot.cmd_action='none'
                self.bot.cmd_move_x_last='none'
                self.bot.kb.set_command('none none none')
                status='人物定位不稳定，暂停移动和攻击，等待定位恢复'
                if status!=self.bot._graph_status_last:
                    logger.info('[地图导航] '+status);self.bot._graph_status_last=status
                return
            if paused:
                nav.last_progress+=paused
                if nav.transit:nav.deadline+=paused;nav.started+=paused
            if nav.fault:
                # Fault recovery must run even while monsters remain nearby.
                command=nav.step(self.bot.loc_player_global,now,valid=valid)
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=command
                self.bot._combat_hold=False;nav._combat_paused_at=None
                self.bot.kb.set_command(' '.join(command));self.bot.cmd_move_x_last=command[0]
                if nav.status!=self.bot._graph_status_last:
                    logger.info('[地图导航] '+nav.status);self.bot._graph_status_last=nav.status
                return
            self.bot.cmd_move_x=self.bot.cmd_move_y=self.bot.cmd_action='none'
            self.bot._combat_hold=False
            platform=nav.platforms.get(nav.locate(self.bot.loc_player_global),{}) if hasattr(nav,'platforms') else {}
            if platform.get('reset_point'):
                command=nav.step(self.bot.loc_player_global,now,valid=valid)
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=command
                self.bot.kb.set_command(' '.join(command));self.bot.cmd_move_x_last=command[0]
                if nav.status!=self.bot._graph_status_last:
                    logger.info('[复位点离开] '+nav.status);self.bot._graph_status_last=nav.status
                return
            # Finish an ongoing climb/jump before engaging. Detect before starting a new transfer.
            sweep=getattr(nav,'platform_sweep',None)
            redirected=False
            if sweep and not nav.transit and valid and now>=getattr(nav,'_slope_air_until',0):
                here=nav.locate(self.bot.loc_player_global)
                if here:redirected=sweep.redirect_to_crowd(nav.graph,here,self.bot.loc_player_global,now)
                if redirected:
                    from src.states.combat_hold import CombatHold
                    self.bot._combat_tracker=CombatHold()
                    logger.info(f'[探索] {sweep.exploration_reason}' if sweep.explore_target else f'[全屏选点] 优先目标 {sweep.target}' if sweep.urgent_target else '[全屏选点] 当前无可达怪物，恢复平台巡逻')
            if (not nav.transit or nav.fault) and valid and now>=getattr(nav,'_slope_air_until',0):
                # A confirmed platform position overrides stale legacy ladder state.
                self.bot.is_on_ladder=False
                self.bot.update_cmd_by_mob_detection()
            if hasattr(self.bot,'update_visible_hunt') and now>=getattr(nav,'_slope_air_until',0):self.bot.update_visible_hunt(now)
            # A crowded remote destination must not be starved by endless local
            # respawns. Keep brief roadside combat, then reserve a movement window.
            crowd_trip=bool(sweep and sweep.urgent_target and
                nav.locate(self.bot.loc_player_global)!=sweep.urgent_target and
                sweep.live_counts(now).get(sweep.urgent_target,0)>=3)
            exploration_trip=bool(sweep and getattr(sweep,'explore_target',None) and sweep.ends and
                (nav.locate(self.bot.loc_player_global)!=sweep.explore_target or
                 abs(self.bot.loc_player_global[0]-sweep.ends[sweep.stage])>2))
            crowd_trip=crowd_trip or exploration_trip
            damage=getattr(self.bot,'_damage_response',None)
            hurt=damage is not None and damage.recent(now)
            if crowd_trip and self.bot._combat_hold and not hurt:
                since=getattr(nav,'_combat_paused_at',None)
                if since is not None and now-since>=1.2:
                    nav._crowd_depart_until=now+.8
                if now<getattr(nav,'_crowd_depart_until',0):
                    from src.states.combat_hold import CombatHold
                    self.bot._combat_tracker=CombatHold();self.bot._combat_hold=False
                    self.bot.cmd_action='none'
            reposition=None
            damage_wait=(damage is not None and not self.bot._combat_hold and
                         not nav.transit and valid and not nav.fault and
                         now>=getattr(nav,'_slope_air_until',0) and
                         nav.locate(self.bot.loc_player_global) is not None and
                         damage.pause_for_scan(now))
            if damage_wait:
                self.bot._combat_hold=True
                self.bot.cmd_move_x=self.bot.cmd_move_y=self.bot.cmd_action='none'
                self.bot._combat_status='受伤排查：暂停巡逻，轮换检查附近怪物（最多 2.5 秒）'
            if not damage_wait and hasattr(nav,'platforms') and valid and not nav.transit and not nav.fault and now>=getattr(nav,'_slope_air_until',0):
                from src.states.combat_reposition import CombatReposition
                if not hasattr(nav,'combat_reposition'):nav.combat_reposition=CombatReposition()
                pos=self.bot.loc_player_global
                near_rope=any(abs(pos[0]-r['x'])<=2 and r['y1']<=pos[1]<=r['y2'] for r in nav.graph.get('ropes',[]))
                platform=nav.platforms.get(nav.locate(pos)) if not near_rope else None
                reposition=nav.combat_reposition.step(now,pos,platform,self.bot._combat_hold,getattr(self.bot.kb,'n_attack_sent',0))
            if reposition is not None:
                from src.states.combat_hold import CombatHold
                self.bot._combat_tracker=CombatHold();self.bot._combat_hold=False
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=reposition
                nav._combat_paused_at=None;nav.last_progress=now
                if getattr(nav,'horizontal_motion',None):nav.horizontal_motion.cancel()
                nav.status='连续施法后短距离换位，重新识别怪物'
            elif self.bot._combat_hold:
                if getattr(nav,'_combat_paused_at',None) is None:nav._combat_paused_at=now
                if getattr(nav,'horizontal_motion',None):nav.horizontal_motion.cancel()
                # Combat is intentional waiting, not a navigation stall.
                nav.last_progress=now
                nav.status=getattr(self.bot,'_combat_status','停下攻击')
            else:
                if getattr(nav,'_combat_paused_at',None) is not None:
                    duration=max(0,now-nav._combat_paused_at)
                    if nav.transit:nav.deadline+=duration;nav.started+=duration
                    nav.last_progress=now;nav._combat_paused_at=None
                command=nav.step(self.bot.loc_player_global,now,valid=valid)
                self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action=command
            if nav.status != self.bot._graph_status_last:
                logger.info('[地图导航] '+nav.status);self.bot._graph_status_last=nav.status
            self.bot.kb.set_command(' '.join((self.bot.cmd_move_x,self.bot.cmd_move_y,self.bot.cmd_action)))
            self.bot.cmd_move_x_last=self.bot.cmd_move_x
            return
        # 指令来源按挂机方式分派：
        # 2026-09-12：定点模式（stand）已按用户要求删除 —— 站着不动的收益
        # 不如"来回走两步顺便打怪"，统一走巡逻。指令来源只剩路线一条。
        self.bot.update_cmd_by_route()

        # Check if reach goal on route map
        self.bot.check_reach_goal()

        # Get attack commend by detecting mobs near players
        self.bot.update_cmd_by_mob_detection()

        # 卡死处理（2026-09-15 改）
        # 原来固定调 update_cmd_by_random（12 种组合**均匀乱抽**，不知道悬崖在哪）：
        # ① 窄平台上乱抽 = 直接掉下去（实测抽到 right none jump，右边正好是悬崖）；
        # ② 它把真因**盖住**了（随机跳把角色从 (100,122) 踹到 (100,118)，
        #    症状从"在原地蹭"变成"跳到另一层"，日志上看"它动了"，更难查）。
        # 现在按 config 的 watchdog.on_stuck 分派，默认 alert = **不乱动 + 弹置顶提示**。
        if not getattr(self.bot,'_combat_hold',False) and self.bot.is_player_stuck():
            self.bot.handle_stuck()

        # send command to keyboard controller
        self.bot.kb.set_command(self.bot.cmd_move_x + ' ' + \
                                self.bot.cmd_move_y + ' ' + \
                                self.bot.cmd_action)

        # 记录本帧**实际发出**的左右指令（2026-09-12 加）
        # 供下一帧判断「是否已经转向」—— 见 update_cmd_by_mob_detection 的先转身后出招。
        # 必须在 set_command 之后更新，否则记到的是本帧被覆盖前的值。
        self.bot.cmd_move_x_last = self.bot.cmd_move_x
