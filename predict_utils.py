if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        # ==========================================
        # 🌟 Agent 路由：如果用户意图是“预测”
        # ==========================================
        if "预测" in user_input or "未来" in user_input:
            st.markdown("🤖 *收到指令！正在启动 AI 预测引擎...*")
            
            # 1. 找时间列和数值列
            date_cols = [c for c, t in col_types.items() if t == "datetime"]
            num_cols = [c for c, t in col_types.items() if t == "numeric"]
            
            if not date_cols or not num_cols:
                st.error("抱歉，当前数据缺少时间列或数值列，无法进行趋势预测。")
            else:
                # 2. 简单的意图识别：提取要预测的列（默认取第一个数值列）
                target_col = num_cols[0] 
                for col in num_cols:
                    if col in user_input:
                        target_col = col
                        break
                
                # 3. 简单提取天数（默认预测7天）
                days = 7
                import re
                match = re.search(r'(\d+)\s*天', user_input)
                if match:
                    days = int(match.group(1))
                
                st.info(f"📊 正在为您预测 **{target_col}** 未来 **{days}** 天的走势...")
                
                # 4. 调用你的底层预测模块
                fig_pred, msg = create_forecast_chart(df, date_cols[0], target_col, periods=days)
                
                if fig_pred:
                    # 直接把图画在对话框里！
                    st.plotly_chart(fig_pred, use_container_width=True)
                    
                    # 5. 让 AI 看着图写分析总结
                    with st.spinner("AI 正在生成预测分析报告..."):
                        prompt = f"用户要求预测 {target_col} 的未来趋势。系统刚刚生成了一张预测图，显示整体呈【上升/下降】趋势（由于你无法直接看图，请用通用的商业预测话术）。请写一段专业的预测结论和备货建议。"
                        ai_response = st.write_stream(
                            call_llm_chat(api_key, model_name, "数据已载入", [], prompt, "你是一个商业预测专家")
                        )
                else:
                    st.error(msg)

        # ==========================================
        # 🌟 普通对话：走原来的分析逻辑
        # ==========================================
        else:
            summary = build_data_summary(df, col_types)
            recent_history = st.session_state.chat_history[-10:]
            ai_response = st.write_stream(
                call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_input, PROMPT_GENERAL)
            )
    
    st.session_state.chat_history.append({"role": "assistant", "content": "执行完毕"})
    st.rerun()
