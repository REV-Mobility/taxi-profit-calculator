import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import google.generativeai as genai

# ---------------------------------------------------------
# 설정 및 유틸리티
# ---------------------------------------------------------
st.set_page_config(page_title="택시회사 급여 수익성 분석툴 with 레브모빌리티", layout="wide")

# CSS: 노란색 하이라이트 디자인
st.markdown("""
<style>
    div[data-baseweb="input"] {
        background-color: #ffffd0 !important;
        border: 1px solid #dcdcdc !important;
        border-radius: 4px !important;
        color: black !important;
    }
    div[data-baseweb="input"]:focus-within {
        background-color: #fff9c4 !important;
        border: 2px solid #fbc02d !important;
        box-shadow: 0 0 5px rgba(251, 192, 45, 0.5) !important;
    }
    .stNumberInput label, .stTextInput label, .stSelectbox label {
        font-weight: 800 !important;
        color: #2d3436 !important;
        font-size: 15px !important;
    }
    button[data-baseweb="tab"] {
        font-weight: bold !important;
        font-size: 16px !important;
    }
</style>
""", unsafe_allow_html=True)

def currency_input(label, value, step=10000, key=None):
    if key and key in st.session_state:
        value = st.session_state[key]
    val = st.number_input(label, value=value, step=step, format="%d", key=key)
    if val > 0:
        st.caption(f"👉 {int(val):,} 원") 
    return val

# 데이터 로드 콜백
def load_data_callback():
    uploaded_file = st.session_state.loader_widget
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            for key, value in data['basic_info'].items():
                st.session_state[key] = value
            st.session_state.scenarios = data['scenarios']
            st.toast("✅ 데이터가 성공적으로 복구되었습니다!", icon="📂")
        except Exception as e:
            st.error(f"데이터 파일 읽기 실패: {e}")

# [NEW] AI 모델 자동 매칭 함수 (오류 방지용)
def get_ai_response(api_key, prompt):
    genai.configure(api_key=api_key)
    
    # 시도할 모델 리스트 (우선순위 순)
    candidate_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    last_error = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text, model_name # 성공하면 텍스트와 모델명 반환
        except Exception as e:
            last_error = e
            continue # 실패하면 다음 모델 시도
            
    raise last_error # 모든 모델 실패 시 에러 발생

st.title("🚖 택시회사 급여 수익성 분석툴 with 레브모빌리티")
st.markdown("---")

# ---------------------------------------------------------
# 1. 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("1. 회사 기초 환경 설정")
    st.markdown("👇 **노란색 칸**에 회사 데이터를 입력하세요.")
    
    with st.expander("① 인력 및 차량 구성", expanded=True):
        col1, col2 = st.columns(2)
        n_day = col1.number_input("주간 기사 수", value=0, key="n_day")
        n_night = col2.number_input("야간 기사 수", value=0, key="n_night")
        n_shift = col1.number_input("교대 기사 수", value=0, key="n_shift")
        n_daily = col2.number_input("일차 기사 수", value=0, key="n_daily")
        
        total_drivers = n_day + n_night + n_shift + n_daily
        st.write(f"**총 기사 수: {total_drivers}명**")
        n_cars = st.number_input("차량 등록 대수", value=0, key="n_cars")

    with st.expander("② 차량 및 운영 비용 (VAT 포함값)", expanded=True):
        st.info("내부 계산 시 /1.1 하여 공급가액만 비용 반영함")
        car_price = currency_input("차량 구입비", 0, step=1000000, key="car_price")
        car_dep_years = st.number_input("감가상각년수 (년)", value=0, key="car_dep_years")
        car_maint = currency_input("차량 유지비 (1대/월)", 0, step=10000, key="car_maint")
        insurance_year = currency_input("보험료 (1대/연간-면세)", 0, step=10000, key="insurance_year")
        
        st.markdown("---")
        rent_cost = currency_input("차고지 임대료 (월)", 0, step=100000, key="rent_cost")
        admin_salary_total = currency_input("관리 직원 급여 (월)", 0, step=500000, key="admin_salary_total")
        
    with st.expander("③ 연료 및 지급 기준", expanded=True):
        full_days = st.number_input("월 만근 일수", value=0, key="full_days")
        lpg_price = st.number_input("LPG 단가 (원/L - VAT포함)", value=0, key="lpg_price")
        
        st.write("1일 평균 연료량(L)")
        c1, c2 = st.columns(2)
        fuel_day = c1.number_input("주간 연료", value=0, key="fuel_day")
        fuel_night = c2.number_input("야간 연료", value=0, key="fuel_night")
        fuel_shift = c1.number_input("교대 연료", value=0, key="fuel_shift")
        fuel_daily = c2.number_input("일차 연료", value=0, key="fuel_daily")

    with st.expander("④ 2026년 4대보험 요율 (고정값)", expanded=True):
        st.caption("※ 2026년 기준 요율 (수정 가능)")
        rate_pension = st.number_input("국민연금 (%)", value=4.75, format="%.2f", key="rate_pension") / 100
        rate_health = st.number_input("건강보험 (%)", value=3.595, format="%.3f", key="rate_health") / 100
        rate_care_ratio = st.number_input("장기요양(건보료비례 %)", value=13.14, format="%.2f", key="rate_care_ratio") / 100
        st.markdown("---")
        rate_emp_unemp = st.number_input("실업급여요율 (%)", value=0.90, format="%.2f", key="rate_emp_unemp") / 100
        rate_emp_stabil = st.number_input("고용안정/직능 (%)", value=0.25, format="%.2f", key="rate_emp_stabil") / 100
        rate_sanjae = st.number_input("산재보험 (%)", value=0.65, format="%.2f", key="rate_sanjae") / 100

# ---------------------------------------------------------
# 2. 시나리오 입력
# ---------------------------------------------------------
st.header("2. 시나리오 등록")

if 'scenarios' not in st.session_state:
    st.session_state.scenarios = []

if 'form_id' not in st.session_state:
    st.session_state.form_id = 0

with st.form("scenario_form"):
    st.write("👇 **아래 노란색 칸에 시나리오 정보를 입력하세요.**")
    c_name, c_wage, c_time = st.columns([2, 1, 1])
    s_name = c_name.text_input("시나리오 이름", "", key=f"reg_name_{st.session_state.form_id}")
    s_hourly = c_wage.number_input("통상 시급(원)", value=0, format="%d", key=f"reg_hourly_{st.session_state.form_id}")
    s_work_time = c_time.number_input("1일 소정근로(시간)", value=0.0, step=0.1, format="%.2f", key=f"reg_time_{st.session_state.form_id}")

    st.markdown("---")
    h1, h2, h3, h4 = st.columns([1, 2, 2, 2])
    h1.markdown("**구분**")
    h2.markdown("**월 급여 총액 (비과세 포함)**")
    h3.markdown("**비과세 금액(예. 야간수당)**")
    h4.markdown("**🔴 1일 사납금**")

    def input_row(label, key_prefix):
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.markdown(f"###### {label}")
        fid = st.session_state.form_id
        pay = c2.number_input(f"{label}총액", value=0, step=10000, label_visibility="collapsed", key=f"reg_pay_{key_prefix}_{fid}")
        tf = c3.number_input(f"{label}비과세", value=0, step=10000, label_visibility="collapsed", key=f"reg_tf_{key_prefix}_{fid}")
        sanap = c4.number_input(f"{label}사납금", value=0, step=1000, label_visibility="collapsed", key=f"reg_sanap_{key_prefix}_{fid}")
        return pay, tf, sanap

    sal_day, tf_day, sanap_day = input_row("주간", "day")
    sal_night, tf_night, sanap_night = input_row("야간", "night")
    sal_shift, tf_shift, sanap_shift = input_row("교대", "shift")
    sal_daily, tf_daily, sanap_daily = input_row("일차", "daily")

    if st.form_submit_button("💾 시나리오 추가"):
        if s_name == "":
            st.error("시나리오 이름을 입력해주세요.")
        else:
            st.session_state.scenarios.append({
                "name": s_name, 
                "hourly": s_hourly,
                "work_time": s_work_time,
                "day": {"pay": sal_day, "tf": tf_day, "sanap": sanap_day},
                "night": {"pay": sal_night, "tf": tf_night, "sanap": sanap_night},
                "shift": {"pay": sal_shift, "tf": tf_shift, "sanap": sanap_shift},
                "daily": {"pay": sal_daily, "tf": tf_daily, "sanap": sanap_daily},
            })
            st.success(f"[{s_name}] 추가되었습니다.")
            st.session_state.form_id += 1
            st.rerun()

# ---------------------------------------------------------
# 3. 계산 및 결과 출력
# ---------------------------------------------------------
st.markdown("---")
st.header("3. 상세 검증 및 분석")

if st.session_state.scenarios:
    # --- 공통 비용 및 단위 계산 ---
    net_rent_cost = rent_cost / 1.1
    per_person_rent = net_rent_cost / total_drivers if total_drivers > 0 else 0
    per_person_admin = admin_salary_total / total_drivers if total_drivers > 0 else 0
    cost_overhead = per_person_rent + per_person_admin

    def get_car_cost_details(driver_type):
        ratio = 1.0 if driver_type == 'single' else 0.5
        net_car_price = car_price / 1.1
        net_car_maint = car_maint / 1.1
        c_dep = (net_car_price / car_dep_years / 12) * ratio if car_dep_years > 0 else 0
        c_ins = (insurance_year / 12) * ratio 
        c_maint = net_car_maint * ratio
        return c_dep, c_ins, c_maint

    def calculate_scenario(sc_data, override_sanap=None):
        hourly_wage = sc_data['hourly']
        work_time_sc = sc_data['work_time']
        
        s_day = override_sanap['day'] if override_sanap else sc_data['day']['sanap']
        s_night = override_sanap['night'] if override_sanap else sc_data['night']['sanap']
        s_shift = override_sanap['shift'] if override_sanap else sc_data['shift']['sanap']
        s_daily = override_sanap['daily'] if override_sanap else sc_data['daily']['sanap']

        types = [
            ("주간", n_day, s_day, fuel_day, sc_data['day']['pay'], sc_data['day']['tf'], 'shared'),
            ("야간", n_night, s_night, fuel_night, sc_data['night']['pay'], sc_data['night']['tf'], 'shared'),
            ("교대", n_shift, s_shift, fuel_shift, sc_data['shift']['pay'], sc_data['shift']['tf'], 'shared'),
            ("일차", n_daily, s_daily, fuel_daily, sc_data['daily']['pay'], sc_data['daily']['tf'], 'single')
        ]

        total_profit = 0
        total_revenue = 0
        total_labor = 0
        details = []
        debug_rows = {}

        for t_name, count, sanap, fuel, pay, tf, d_type in types:
            if count == 0: continue
            
            monthly_sanap = sanap * full_days
            vat_out = monthly_sanap * (10 / 110)
            card_fee = monthly_sanap * 0.015
            fuel_liter = fuel * full_days
            net_fuel_cost = fuel_liter * (lpg_price / 1.1)
            
            c_dep, c_ins, c_maint = get_car_cost_details(d_type)
            total_car_fixed = c_dep + c_ins + c_maint
            
            total_pay = pay
            taxable_pay = pay - tf
            if taxable_pay < 0: taxable_pay = 0
            severance = total_pay / 12 
            annual_leave = hourly_wage * work_time_sc * 1.25
            
            ins_pension = taxable_pay * rate_pension
            ins_health = taxable_pay * rate_health
            ins_care = ins_health * rate_care_ratio
            ins_emp = taxable_pay * (rate_emp_unemp + rate_emp_stabil)
            ins_sanjae = total_pay * rate_sanjae
            total_4ins = ins_pension + ins_health + ins_care + ins_emp + ins_sanjae
            total_labor_cost = total_pay + severance + annual_leave + total_4ins
            
            total_cost_person = (vat_out + card_fee + net_fuel_cost + total_car_fixed + total_labor_cost + cost_overhead)
            profit_person = monthly_sanap - total_cost_person
            
            group_profit = profit_person * count
            total_profit += group_profit
            total_revenue += (monthly_sanap * count)
            total_labor += (total_labor_cost * count)
            
            labor_ratio = (total_labor_cost / monthly_sanap * 100) if monthly_sanap > 0 else 0
            
            details.append({
                "근무형태": t_name,
                "1인 매출": monthly_sanap,
                "1인 영업이익": profit_person,
                "1인 인건비": total_labor_cost,
                "인건비율": labor_ratio
            })
            
            rows = []
            rows.append(("1. 월 매출(사납금)", monthly_sanap, f"{sanap:,}원 × {full_days}일"))
            rows.append(("▼ 매출 공제(세금/수수료)", -(vat_out + card_fee), ""))
            rows.append(("   └ 부가세(매출세액)", -vat_out, "사납금의 10/110"))
            rows.append(("   └ 카드수수료", -card_fee, "사납금의 1.5%"))
            rows.append(("▼ 연료비(Net)", -net_fuel_cost, "부가세 제외 공급가 기준"))
            rows.append(("▼ 차량 고정비 합계", -total_car_fixed, "감가+보험+유지"))
            rows.append(("   └ 감가상각비", -c_dep, ""))
            rows.append(("   └ 보험료", -c_ins, ""))
            rows.append(("   └ 유지비", -c_maint, ""))
            rows.append(("▼ 인건비 합계", -total_labor_cost, f"매출 대비 {labor_ratio:.1f}%"))
            rows.append(("   └ 급여 지급액(Gross)", -total_pay, "입력된 총액"))
            rows.append(("   └ 퇴직금 적립액", -severance, "급여총액 ÷ 12"))
            rows.append(("   └ 연차수당", -annual_leave, f"{hourly_wage:,}원×{work_time_sc}h×1.25"))
            rows.append(("   ▼ [상세] 4대보험 계", -total_4ins, ""))
            rows.append(("      - 국민연금", -ins_pension, f"{rate_pension*100:.2f}%"))
            rows.append(("      - 건강보험", -ins_health, f"{rate_health*100:.3f}%"))
            rows.append(("      - 장기요양", -ins_care, f"건보료의 {rate_care_ratio*100:.2f}%"))
            rows.append(("      - 고용보험", -ins_emp, f"{(rate_emp_unemp+rate_emp_stabil)*100:.2f}%"))
            rows.append(("      - 산재보험", -ins_sanjae, f"{rate_sanjae*100:.2f}%"))
            rows.append(("▼ 공통 운영비 합계", -cost_overhead, ""))
            rows.append(("   └ 차고지 임대료", -per_person_rent, ""))
            rows.append(("   └ 관리직원 급여", -per_person_admin, ""))
            rows.append(("■ 최종 영업이익", profit_person, "매출 - 비용합계"))
            debug_rows[f"{sc_data['name']} - {t_name}"] = rows

        profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        labor_margin = (total_labor / total_revenue * 100) if total_revenue > 0 else 0
        
        return {
            "name": sc_data['name'],
            "revenue": total_revenue,
            "profit": total_profit,
            "labor": total_labor,
            "margin": profit_margin,
            "labor_rate": labor_margin,
            "details": details,
            "debug": debug_rows
        }

    all_results_data = [calculate_scenario(sc) for sc in st.session_state.scenarios]
    global_debug = {}
    for res in all_results_data:
        global_debug.update(res['debug'])

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎛️ 사납금 조정", "🏆 시나리오 비교", "📊 근무형태별 분석", "🧾 상세 계산 검증", "🤖 AI 경영 컨설팅"
    ])

    with tab1:
        st.subheader("🎛️ 사납금 조정 시뮬레이터 (What-If)")
        sc_names = [sc['name'] for sc in st.session_state.scenarios]
        selected_sc_name = st.selectbox("조정할 시나리오 선택", sc_names)
        
        selected_sc_idx = sc_names.index(selected_sc_name)
        origin_sc = st.session_state.scenarios[selected_sc_idx]
        
        st.write(f"▼ **'{selected_sc_name}'의 1일 사납금을 조정해 보세요.**")
        ac1, ac2, ac3, ac4 = st.columns(4)
        
        new_day = ac1.number_input("주간 사납금", value=origin_sc['day']['sanap'], step=1000, key=f"sim_day_{selected_sc_idx}")
        new_night = ac2.number_input("야간 사납금", value=origin_sc['night']['sanap'], step=1000, key=f"sim_night_{selected_sc_idx}")
        new_shift = ac3.number_input("교대 사납금", value=origin_sc['shift']['sanap'], step=1000, key=f"sim_shift_{selected_sc_idx}")
        new_daily = ac4.number_input("일차 사납금", value=origin_sc['daily']['sanap'], step=1000, key=f"sim_daily_{selected_sc_idx}")
        
        override_map = {'day': new_day, 'night': new_night, 'shift': new_shift, 'daily': new_daily}
        sim_result = calculate_scenario(origin_sc, override_map)
        origin_result = all_results_data[selected_sc_idx]
        
        st.markdown("##### 📊 시뮬레이션 결과")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("월 총 매출", f"{sim_result['revenue']:,.0f} 원", f"{sim_result['revenue'] - origin_result['revenue']:,.0f} 원")
        mc2.metric("월 영업이익", f"{sim_result['profit']:,.0f} 원", f"{sim_result['profit'] - origin_result['profit']:,.0f} 원")
        mc3.metric("영업이익률", f"{sim_result['margin']:.2f} %", f"{sim_result['margin'] - origin_result['margin']:.2f} %p")
        mc4.metric("인건비율", f"{sim_result['labor_rate']:.2f} %", f"{sim_result['labor_rate'] - origin_result['labor_rate']:.2f} %p", delta_color="inverse")
        
        st.markdown("---")
        if st.button("💾 변경된 사납금으로 이 시나리오 업데이트"):
            st.session_state.scenarios[selected_sc_idx]['day']['sanap'] = new_day
            st.session_state.scenarios[selected_sc_idx]['night']['sanap'] = new_night
            st.session_state.scenarios[selected_sc_idx]['shift']['sanap'] = new_shift
            st.session_state.scenarios[selected_sc_idx]['daily']['sanap'] = new_daily
            st.success("✅ 업데이트 완료!")
            st.rerun()

    with tab2:
        st.subheader("🏆 시나리오 총괄 비교표")
        summary_rows = []
        for res in all_results_data:
            summary_rows.append({
                "시나리오명": res['name'],
                "총 매출": res['revenue'],
                "총 인건비": res['labor'],
                "영업이익": res['profit'],
                "인건비율": res['labor_rate'],
                "이익률": res['margin']
            })
        df_summary = pd.DataFrame(summary_rows)
        st.dataframe(df_summary.style.format({
                "총 매출": "{:,.0f}", "총 인건비": "{:,.0f}", "영업이익": "{:,.0f}", 
                "인건비율": "{:.1f}%", "이익률": "{:.1f}%"
            }).background_gradient(subset=["영업이익", "이익률"], cmap="Greens").background_gradient(subset=["총 인건비", "인건비율"], cmap="Reds"), use_container_width=True)

    with tab3:
        st.subheader("🧐 근무 형태별 수익성 상세")
        if all_results_data:
            target_sc = st.selectbox("분석할 시나리오", sc_names, key="tab3_sel")
            target_res = next(r for r in all_results_data if r['name'] == target_sc)
            df_detail = pd.DataFrame(target_res['details'])
            c1, c2 = st.columns(2)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(name='1인 매출', x=df_detail['근무형태'], y=df_detail['1인 매출'], text=df_detail['1인 매출'], texttemplate='%{text:,.0f}'))
            fig_bar.add_trace(go.Bar(name='1인 이익', x=df_detail['근무형태'], y=df_detail['1인 영업이익'], text=df_detail['1인 영업이익'], texttemplate='%{text:,.0f}'))
            fig_bar.update_layout(title=f"[{target_sc}] 1인당 실적 비교", barmode='group')
            c1.plotly_chart(fig_bar, use_container_width=True)
            fig_rate = px.bar(df_detail, x='근무형태', y='인건비율', color='근무형태', text='인건비율', title=f"[{target_sc}] 인건비율 (%)")
            fig_rate.update_traces(texttemplate='%{text:.1f}%')
            c2.plotly_chart(fig_rate, use_container_width=True)

    with tab4:
        st.info("💡 **[▼]** 표시된 항목은 합계, **[└]** 는 상세 내역입니다.")
        selected_key = st.selectbox("검증할 대상", list(global_debug.keys()))
        if selected_key:
            records = global_debug[selected_key]
            df_debug = pd.DataFrame(records, columns=["항목", "금액(원)", "비고"])
            def highlight_row(row):
                if "최종" in row["항목"]: return ['background-color: #dff9fb; font-weight: bold; color: black'] * len(row)
                elif "▼" in row["항목"]: return ['background-color: #f1f2f6; font-weight: bold; color: #2c3e50'] * len(row)
                elif row["금액(원)"] < 0: return ['background-color: white; color: #c0392b'] * len(row)
                else: return ['background-color: white; color: #2980b9'] * len(row)
            st.dataframe(df_debug.style.apply(highlight_row, axis=1).format({"금액(원)": "{:,.0f}"}), use_container_width=True, height=800)

    with tab5:
        st.subheader("🤖 AI 경영 컨설턴트 (Powered by Gemini)")
        st.markdown("입력된 시나리오 데이터를 분석하여 **수익 개선 전략**을 제안합니다.")
        api_key = st.text_input("Google API Key를 입력하세요", type="password")
        
        if st.button("AI 분석 요청하기"):
            if not api_key:
                st.error("API Key가 필요합니다.")
            else:
                try:
                    # [NEW] 모델명을 자동/순차적으로 시도하는 함수 호출
                    response_text, model_name = get_ai_response(api_key, f"""
                    당신은 전문적인 택시 회사 경영 컨설턴트입니다.
                    아래는 택시 회사의 시나리오별 예상 수익 분석입니다.
                    [데이터 요약]
                    {summary_rows}
                    
                    다음 내용을 포함한 보고서를 한국어로 작성해주세요:
                    1. **최고의 시나리오 추천:** 이익이 가장 좋은 안은 무엇인가요?
                    2. **리스크 분석:** 인건비율이 적정한가요?
                    3. **전략 제안:** 경영진이 고려해야 할 구체적인 개선점은?
                    """)
                    
                    st.success(f"✅ 분석 완료! (사용된 모델: {model_name})")
                    st.markdown(response_text)
                    
                except Exception as e:
                    st.error(f"AI 오류: {e}")

else:
    st.info("👈 왼쪽 사이드바에서 시나리오를 등록해주세요.")

# ---------------------------------------------------------
# [하단] 데이터 저장/불러오기
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("---")
    st.header("📂 데이터 저장 / 불러오기")
    
    # [핵심] 콜백 함수 등록 (on_change=load_data_callback)
    st.file_uploader(
        "저장된 파일 열기 (JSON)", 
        type=["json"], 
        key="loader_widget", 
        on_change=load_data_callback
    )

    def get_current_data():
        keys_to_save = [
            'n_day', 'n_night', 'n_shift', 'n_daily', 'n_cars',
            'car_price', 'car_dep_years', 'car_maint', 'insurance_year',
            'rent_cost', 'admin_salary_total',
            'full_days', 'lpg_price',
            'fuel_day', 'fuel_night', 'fuel_shift', 'fuel_daily',
            'rate_pension', 'rate_health', 'rate_care_ratio', 
            'rate_emp_unemp', 'rate_emp_stabil', 'rate_sanjae'
        ]
        basic_info = {}
        for k in keys_to_save:
            if k in st.session_state:
                basic_info[k] = st.session_state[k]
        
        return json.dumps({
            "basic_info": basic_info,
            "scenarios": st.session_state.get('scenarios', [])
        }, indent=4, ensure_ascii=False)

    st.download_button(
        label="💾 작업 내용 PC 저장",
        data=get_current_data(),
        file_name="taxi_profit_data.json",
        mime="application/json"
    )
