import streamlit as st
import streamlit_player_testing_functions as pf


st.set_page_config(layout="wide")
st.title("NBA Player Data")
with st.container(height=500, border=True):
    st.image(pf.headshot,
             width=500,
             caption='Anthony Edwards')

with st.container(height=1000, border=True):
    st.altair_chart(pf.final_chart, width='content')