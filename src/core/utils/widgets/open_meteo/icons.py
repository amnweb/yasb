"""
Inline SVG weather icons and WMO weather code mapping for OpenMeteoWidget.

WMO Weather interpretation codes (WW):
  0: Clear sky
  1, 2, 3: Mainly clear, Partly cloudy, Overcast
  45, 48: Fog, Depositing rime fog
  51, 53, 55: Drizzle (light, moderate, dense)
  56, 57: Freezing drizzle (light, dense)
  61, 63, 65: Rain (slight, moderate, heavy)
  66, 67: Freezing rain (light, heavy)
  71, 73, 75: Snow fall (slight, moderate, heavy)
  77: Snow grains
  80, 81, 82: Rain showers (slight, moderate, violent)
  85, 86: Snow showers (slight, heavy)
  95: Thunderstorm (slight or moderate)
  96, 99: Thunderstorm with hail (slight, heavy)
"""

#  SVG Icon Constants

SVG_SUNNY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="877.03" y1="-1100.58" x2="847.89" y2="-1065.01" gradientTransform="matrix(1, 0, 0, -1, -846, -1068)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ed6e23"/><stop offset="0.56" stop-color="#edb828"/><stop offset="1" stop-color="#fbb448" stop-opacity="0.78"/></linearGradient></defs><circle cx="24" cy="24" r="17.87" fill="url(#a)"/></svg>"""

SVG_CLEAR_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="1726.89" y1="-2251.57" x2="1729.94" y2="-2180.14" gradientTransform="matrix(0.5, 0, 0, -0.5, -840, -1086)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ee7f18"/><stop offset="0.56" stop-color="#eeb82e"/><stop offset="1" stop-color="#feb649" stop-opacity="0.78"/></linearGradient></defs><path d="M13.2,29.86a16.91,16.91,0,0,0,16-22.3,1.12,1.12,0,0,1,.63-1.44,1.08,1.08,0,0,1,.75,0A18.63,18.63,0,1,1,6.05,30.19a1.11,1.11,0,0,1,.72-1.38h0a1.16,1.16,0,0,1,.78,0,16.92,16.92,0,0,0,5.64,1.05" fill-rule="evenodd" fill="url(#a)"/></svg>"""

SVG_CLOUDY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="622.08" y1="-729.39" x2="592.73" y2="-693.56" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ef6d0f"/><stop offset="0.56" stop-color="#eeb82e"/><stop offset="1" stop-color="#feb649" stop-opacity="0.78"/></linearGradient><linearGradient id="b" x1="591.69" y1="-724.72" x2="605.19" y2="-759.22" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="c" x1="600.34" y1="-762.76" x2="599.39" y2="-716.16" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="d" cx="-32.65" cy="48.29" r="1" gradientTransform="matrix(-8.75, -11.25, -13.02, 10.13, 358.67, -817.66)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="e" cx="-18.28" cy="34.07" r="1" gradientTransform="matrix(0, -20.25, -20.25, 0, 713.25, -333.86)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="f" cx="-9.56" cy="20.26" r="1" gradientTransform="matrix(8.8, -13.2, -13.2, -8.8, 380.95, 88.59)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient></defs><circle cx="31.5" cy="18.37" r="9" fill="url(#a)"/><path d="M12.75,38.62h21a8.25,8.25,0,1,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.75,38.62h21a8.25,8.25,0,1,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M12.75,38.62h21a8.25,8.25,0,1,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#c)"/><path d="M6,31.87a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.75A6.75,6.75,0,0,1,6,31.87" fill="url(#d)"/><path d="M12,27.37A11.25,11.25,0,1,1,23.25,38.62,11.25,11.25,0,0,1,12,27.37" fill="url(#e)"/><circle cx="33.75" cy="30.37" r="8.25" fill="url(#f)"/></svg>"""

SVG_CLOUDY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="583.99" y1="-735.14" x2="585.66" y2="-695.76" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ee7f18"/><stop offset="0.56" stop-color="#eeb82e"/><stop offset="1" stop-color="#feb649" stop-opacity="0.78"/></linearGradient><linearGradient id="b" x1="591.69" y1="-729.59" x2="605.19" y2="-764.09" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="c" x1="600.34" y1="-767.62" x2="599.39" y2="-721.03" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="d" cx="-32.78" cy="48.37" r="1" gradientTransform="matrix(-8.75, -11.25, -13.02, 10.13, 358.67, -817.55)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="e" cx="-18.4" cy="34.07" r="1" gradientTransform="matrix(0, -20.25, -20.25, 0, 713.25, -333.75)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="f" cx="-9.68" cy="20.18" r="1" gradientTransform="matrix(8.8, -13.2, -13.2, -8.8, 380.95, 88.7)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient></defs><path d="M10.12,20a9.47,9.47,0,0,0,9.44-9.48,9.76,9.76,0,0,0-.25-2.17c-.2-.84.55-1.69,1.32-1.28A10.45,10.45,0,1,1,6.46,21c-.38-.78.48-1.51,1.32-1.3a9.5,9.5,0,0,0,2.34.3" fill-rule="evenodd" fill="url(#a)"/><path d="M12.75,41.06h21a8.25,8.25,0,0,0,0-16.5,4.87,4.87,0,0,0-.54,0,11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.75,41.06h21a8.25,8.25,0,0,0,0-16.5,4.87,4.87,0,0,0-.54,0,11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M12.75,41.06h21a8.25,8.25,0,0,0,0-16.5,4.87,4.87,0,0,0-.54,0,11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#c)"/><path d="M6,34.31a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.75A6.75,6.75,0,0,1,6,34.31" fill="url(#d)"/><path d="M12,29.81A11.25,11.25,0,1,1,23.25,41.06,11.25,11.25,0,0,1,12,29.81" fill="url(#e)"/><circle cx="33.75" cy="32.81" r="8.25" fill="url(#f)"/></svg>"""

SVG_FOGGY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="591.7" y1="754.94" x2="605.2" y2="789.44" gradientTransform="translate(-276 -366) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="b" x1="600.34" y1="792.96" x2="599.39" y2="746.37" gradientTransform="translate(-276 -366) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="c" cx="-32.16" cy="0.05" r="1" gradientTransform="matrix(-8.75, -11.25, 13.02, -10.13, -266.29, -331.42)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="d" cx="-17.85" cy="13.93" r="1" gradientTransform="translate(-258.75 -333.86) rotate(-90) scale(20.25)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="e" cx="-9.09" cy="27.43" r="1" gradientTransform="translate(-252.65 -333.81) rotate(-56.31) scale(15.86)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="f" x1="1163.31" y1="1557" x2="1164.74" y2="1539.53" gradientTransform="translate(-558 -738) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#84a6e7"/><stop offset="1" stop-color="#cfe0f3"/></linearGradient></defs><path d="M12.76,29.73h21a8.25,8.25,0,0,0,0-16.5h-.54a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.76,29.73h21a8.25,8.25,0,0,0,0-16.5h-.54a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#a)"/><path d="M12.76,29.73h21a8.25,8.25,0,0,0,0-16.5h-.54a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M6,23a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.76A6.75,6.75,0,0,1,6,23v0" fill="url(#c)"/><path d="M12,18.48A11.25,11.25,0,1,1,23.26,29.73,11.25,11.25,0,0,1,12,18.48v0" fill="url(#d)"/><circle cx="33.76" cy="21.48" r="8.25" fill="url(#e)"/><path d="M6,33.31a1.5,1.5,0,0,1,1.5-1.5H27.9a1.5,1.5,0,0,1,0,3H7.52A1.5,1.5,0,0,1,6,33.33v0m27,0a1.5,1.5,0,0,1,1.5-1.5h6a1.5,1.5,0,0,1,0,3h-6a1.5,1.5,0,0,1-1.5-1.5M7.5,37.81a1.5,1.5,0,0,0,0,3h33a1.5,1.5,0,0,0,0-3Z" fill-rule="evenodd" fill="url(#f)"/></svg>"""

SVG_FOGGY_NIGHT = SVG_FOGGY_DAY

SVG_DRIZZLE_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="591.69" y1="-708.97" x2="605.19" y2="-743.47" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="b" x1="600.34" y1="-747.01" x2="599.39" y2="-700.41" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="c" cx="-32.63" cy="48.27" r="1" gradientTransform="matrix(-8.75, -11.25, -13.02, 10.13, 358.67, -825.05)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="d" cx="-18.26" cy="34.07" r="1" gradientTransform="matrix(0, -20.25, -20.25, 0, 713.25, -341.25)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="e" cx="-9.53" cy="20.28" r="1" gradientTransform="matrix(8.8, -13.2, -13.2, -8.8, 380.95, 81.2)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="f" x1="620.01" y1="-760.18" x2="601.05" y2="-739.27" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#06f"/><stop offset="1" stop-color="#65acff"/></linearGradient></defs><path d="M12.75,30.75h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.75,30.75h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#a)"/><path d="M12.75,30.75h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M6,24a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.75A6.75,6.75,0,0,1,6,24" fill="url(#c)"/><path d="M12,19.5A11.25,11.25,0,1,1,23.25,30.75,11.25,11.25,0,0,1,12,19.5" fill="url(#d)"/><circle cx="33.75" cy="22.5" r="8.25" fill="url(#e)"/><path d="M25.5,34.5V24.3a1.05,1.05,0,0,1,1.8-.74l7.12,7.19A5.25,5.25,0,1,1,25.5,34.5" fill="#c4c4c4" fill-rule="evenodd"/><path d="M25.5,34.5V24.3a1.05,1.05,0,0,1,1.8-.74l7.12,7.19A5.25,5.25,0,1,1,25.5,34.5" fill-rule="evenodd" fill="url(#f)"/></svg>"""

SVG_DRIZZLE_NIGHT = SVG_DRIZZLE_DAY

SVG_RAINY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="318.46" y1="-343.35" x2="303.88" y2="-325.54" gradientTransform="matrix(1, 0, 0, -1, -282, -324)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ef6d0f"/><stop offset="0.56" stop-color="#eeb82e"/><stop offset="1" stop-color="#feb649" stop-opacity="0.78"/></linearGradient><linearGradient id="b" x1="301.87" y1="-341.77" x2="308.58" y2="-358.92" gradientTransform="matrix(1, 0, 0, -1, -282, -324)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="c" x1="306.17" y1="-360.68" x2="305.7" y2="-337.52" gradientTransform="matrix(1, 0, 0, -1, -282, -324)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="d" cx="-15.46" cy="47.7" r="0.5" gradientTransform="matrix(-17.5, -22.5, -26.04, 20.25, 987.34, -1278.1)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="e" cx="-8.5" cy="41.31" r="0.5" gradientTransform="matrix(0, -40.5, -40.5, 0, 1696.5, -310.5)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="f" cx="-4.4" cy="35.04" r="0.5" gradientTransform="matrix(17.6, -26.4, -26.4, -17.6, 1031.9, 534.4)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="g" x1="318.93" y1="-364.24" x2="309.5" y2="-353.85" gradientTransform="matrix(1, 0, 0, -1, -282, -324)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#06f"/><stop offset="1" stop-color="#65acff"/></linearGradient><linearGradient id="h" x1="304.29" y1="-363.02" x2="296.37" y2="-354.14" xlink:href="#g"/></defs><circle cx="32.95" cy="15.05" r="8.95" fill="url(#a)"/><path d="M12.82,35.93H33.69a8.2,8.2,0,1,0,0-16.4h-.53a11.19,11.19,0,0,0-20.87,3,6.71,6.71,0,0,0,.53,13.4Z" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.82,35.93H33.69a8.2,8.2,0,1,0,0-16.4h-.53a11.19,11.19,0,0,0-20.87,3,6.71,6.71,0,0,0,.53,13.4Z" fill-rule="evenodd" fill="url(#b)"/><path d="M12.82,35.93H33.69a8.2,8.2,0,1,0,0-16.4h-.53a11.19,11.19,0,0,0-20.87,3,6.71,6.71,0,0,0,.53,13.4Z" fill-rule="evenodd" fill="url(#c)"/><path d="M6.11,29.22a6.7,6.7,0,0,1,6.71-6.71h2.23a9,9,0,0,1,9,8.94v4.48H12.82A6.71,6.71,0,0,1,6.11,29.22Z" fill="url(#d)"/><path d="M12.07,24.75A11.19,11.19,0,1,1,23.25,35.93,11.19,11.19,0,0,1,12.07,24.75Z" fill="url(#e)"/><circle cx="33.69" cy="27.73" r="8.2" fill="url(#f)"/><path d="M28.47,36.67V26.53a1,1,0,0,1,1.79-.73l7.08,7.14a5.22,5.22,0,1,1-8.87,3.73Z" fill="#c4c4c4" fill-rule="evenodd"/><path d="M28.47,36.67V26.53a1,1,0,0,1,1.79-.73l7.08,7.14a5.22,5.22,0,1,1-8.87,3.73Z" fill-rule="evenodd" fill="url(#g)"/><path d="M15.05,35.65v-8a1,1,0,0,1,1.79-.73l5.47,5.52a4.47,4.47,0,1,1-7.26,3.5c0-.1,0-.19,0-.28Z" fill="#c4c4c4" fill-rule="evenodd"/><path d="M15.05,35.65v-8a1,1,0,0,1,1.79-.73l5.47,5.52a4.47,4.47,0,1,1-7.26,3.5c0-.1,0-.19,0-.28Z" fill-rule="evenodd" fill="url(#h)"/></svg>"""

SVG_RAINY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="1148.1" y1="1525.68" x2="1149.78" y2="1486.3" gradientTransform="translate(-558 -738) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ee7f18"/><stop offset="0.56" stop-color="#eeb82e"/><stop offset="1" stop-color="#feb649" stop-opacity="0.78"/></linearGradient><linearGradient id="b" x1="1155.69" y1="1520.12" x2="1169.19" y2="1554.62" gradientTransform="translate(-558 -738) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="c" x1="1164.34" y1="1558.16" x2="1163.39" y2="1511.57" gradientTransform="translate(-558 -738) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="d" cx="-65.5" cy="-0.69" r="1" gradientTransform="matrix(-8.75, -11.25, 13.02, -10.13, -548.29, -703.31)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="e" cx="-36.73" cy="27.85" r="1" gradientTransform="translate(-540.75 -705.75) rotate(-90) scale(20.25)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="f" cx="-19.29" cy="55.59" r="1" gradientTransform="translate(-534.65 -705.7) rotate(-56.31) scale(15.86)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="g" x1="1190.02" y1="1556.35" x2="1171.05" y2="1535.45" gradientTransform="translate(-558 -738) scale(0.5)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#06f"/><stop offset="1" stop-color="#65acff"/></linearGradient><linearGradient id="h" x1="1160.58" y1="1553.88" x2="1144.64" y2="1536" xlink:href="#g"/></defs><path d="M10.13,19.21a9.46,9.46,0,0,0,9.44-9.47,9.32,9.32,0,0,0-.25-2.17c-.2-.84.56-1.69,1.32-1.29A10.45,10.45,0,1,1,6.49,20.21c-.38-.78.48-1.51,1.32-1.3a9.74,9.74,0,0,0,2.34.29" fill-rule="evenodd" fill="url(#a)"/><path d="M12.76,40.33h21a8.25,8.25,0,1,0,0-16.5h-.54a11.26,11.26,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.76,40.33h21a8.25,8.25,0,1,0,0-16.5h-.54a11.26,11.26,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M12.76,40.33h21a8.25,8.25,0,1,0,0-16.5h-.54a11.26,11.26,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#c)"/><path d="M6,33.58a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.76A6.75,6.75,0,0,1,6,33.58H6" fill="url(#d)"/><path d="M12,29.08A11.25,11.25,0,1,1,23.26,40.33h0A11.25,11.25,0,0,1,12,29.08" fill="url(#e)"/><circle cx="33.76" cy="32.08" r="8.25" fill="url(#f)"/><path d="M28.49,36.58V26.38a1,1,0,0,1,1.8-.74l7.12,7.18a5.25,5.25,0,1,1-8.92,3.76" fill="#c4c4c4" fill-rule="evenodd"/><path d="M28.49,36.58V26.38a1,1,0,0,1,1.8-.74l7.12,7.18a5.25,5.25,0,1,1-8.92,3.76" fill-rule="evenodd" fill="url(#g)"/><path d="M15,35.55V27.49a1,1,0,0,1,1.8-.74l5.5,5.55A4.5,4.5,0,1,1,15,35.54Z" fill="#c4c4c4" fill-rule="evenodd"/><path d="M15,35.55V27.49a1,1,0,0,1,1.8-.74l5.5,5.55A4.5,4.5,0,1,1,15,35.54Z" fill-rule="evenodd" fill="url(#h)"/></svg>"""

SVG_SNOWY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="591.69" y1="-711.97" x2="605.19" y2="-746.47" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="b" x1="600.34" y1="-750.01" x2="599.39" y2="-703.41" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="c" cx="-32.71" cy="48.32" r="1" gradientTransform="matrix(-8.75, -11.25, -13.02, 10.13, 358.67, -825.05)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="d" cx="-18.33" cy="34.07" r="1" gradientTransform="matrix(0, -20.25, -20.25, 0, 713.25, -341.25)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="e" cx="-9.61" cy="20.23" r="1" gradientTransform="matrix(8.8, -13.2, -13.2, -8.8, 380.95, 81.2)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="f" x1="604.5" y1="-730.5" x2="604.5" y2="-760.5" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#1a70f0"/><stop offset="1" stop-color="#2d94de"/></linearGradient></defs><path d="M12.75,32.25h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill="#e7f1ff" fill-rule="evenodd"/><path d="M12.75,32.25h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#a)"/><path d="M12.75,32.25h21a8.25,8.25,0,0,0,0-16.5l-.54,0a11.25,11.25,0,0,0-21,3,6.75,6.75,0,0,0,.53,13.48" fill-rule="evenodd" fill="url(#b)"/><path d="M6,25.5a6.75,6.75,0,0,1,6.75-6.75H15a9,9,0,0,1,9,9v4.5H12.75A6.75,6.75,0,0,1,6,25.5" fill="url(#c)"/><path d="M12,21A11.25,11.25,0,1,1,23.25,32.25,11.25,11.25,0,0,1,12,21" fill="url(#d)"/><circle cx="33.75" cy="24" r="8.25" fill="url(#e)"/><path d="M26.25,23.25A.76.76,0,0,1,27,24v1.19l.22-.22A.75.75,0,0,1,28.28,26L27,27.31v2.14l1.85-1.07.47-1.75a.75.75,0,0,1,1.45.39l-.08.3,1-.59A.75.75,0,1,1,32.48,28h0l-1,.6.3.08a.75.75,0,1,1-.39,1.45h0l-1.75-.47-1.85,1.07,1.85,1.07,1.75-.47a.75.75,0,1,1,.39,1.45l-.3.08,1,.6a.74.74,0,0,1,.28,1,.75.75,0,0,1-1,.28h0l-1-.59.08.3a.75.75,0,0,1-1.45.39h0l-.47-1.75L27,32.05v2.14l1.28,1.28a.75.75,0,0,1-1.06,1.06L27,36.31V37.5a.75.75,0,0,1-1.5,0V36.31l-.22.22a.75.75,0,0,1-1.06-1.06l1.28-1.28V32.05l-1.85,1.07-.47,1.75a.75.75,0,0,1-1.45-.39l.08-.3-1,.6a.77.77,0,0,1-1-.27.75.75,0,0,1,.27-1h0l1-.6-.3-.08a.75.75,0,1,1,.39-1.45l1.75.47,1.85-1.07L22.9,29.68l-1.75.47a.75.75,0,1,1-.39-1.45l.3-.08L20,28a.74.74,0,0,1-.28-1,.75.75,0,0,1,1-.28h0l1,.59-.08-.3a.75.75,0,1,1,1.44-.42v0l.47,1.75,1.85,1.07V27.31L24.22,26A.75.75,0,0,1,25.28,25l.22.22V24a.76.76,0,0,1,.75-.75" fill-rule="evenodd" fill="url(#f)"/></svg>"""

SVG_SNOWY_NIGHT = SVG_SNOWY_DAY

SVG_THUNDERSTORM_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><defs><linearGradient id="a" x1="593.53" y1="-706.49" x2="606.47" y2="-739.55" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#c6d8f5"/><stop offset="1" stop-color="#89afd1" stop-opacity="0"/></linearGradient><linearGradient id="b" x1="601.82" y1="-742.94" x2="600.92" y2="-698.29" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#547dda"/><stop offset="0.26" stop-color="#93c2ff" stop-opacity="0"/></linearGradient><radialGradient id="c" cx="-34.11" cy="48.32" r="1" gradientTransform="matrix(-8.39, -10.78, -12.48, 9.7, 333.73, -807.89)" gradientUnits="userSpaceOnUse"><stop offset="0.68" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><radialGradient id="d" cx="-19.11" cy="33.47" r="1" gradientTransform="matrix(0, -19.41, -19.41, 0, 673.53, -344.25)" gradientUnits="userSpaceOnUse"><stop offset="0.6" stop-color="#c7dfff" stop-opacity="0"/><stop offset="1" stop-color="#6b97e6"/></radialGradient><radialGradient id="e" cx="-10.01" cy="19.04" r="1" gradientTransform="matrix(8.43, -12.65, -12.65, -8.43, 355.08, 60.6)" gradientUnits="userSpaceOnUse"><stop offset="0.48" stop-color="#8fabdd" stop-opacity="0"/><stop offset="1" stop-color="#5582d3"/></radialGradient><linearGradient id="f" x1="594" y1="-716.19" x2="594" y2="-753.69" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#718ea8"/><stop offset="1" stop-color="#3f6587"/></linearGradient><radialGradient id="g" cx="-38.23" cy="42.56" r="1" gradientTransform="matrix(-5.63, -10.63, -12.3, 6.51, 322.4, -648.49)" gradientUnits="userSpaceOnUse"><stop offset="0.63" stop-color="#b8cddf" stop-opacity="0"/><stop offset="1" stop-color="#a3b9cc"/></radialGradient><radialGradient id="h" cx="-21.97" cy="31.29" r="1" gradientTransform="matrix(0, -16.88, -16.88, 0, 548.46, -337.87)" gradientUnits="userSpaceOnUse"><stop offset="0.69" stop-color="#b8cddf" stop-opacity="0"/><stop offset="1" stop-color="#c1d7ea"/></radialGradient><radialGradient id="i" cx="-11.51" cy="14.7" r="1" gradientTransform="matrix(7.33, -11, -11, -7.33, 271.52, 14.21)" gradientUnits="userSpaceOnUse"><stop offset="0.38" stop-color="#b8cddf" stop-opacity="0"/><stop offset="1" stop-color="#a3b9cc"/></radialGradient><linearGradient id="j" x1="601.19" y1="-758.6" x2="587.86" y2="-741.9" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#e25a01"/><stop offset="1" stop-color="#ffd400"/></linearGradient><linearGradient id="k" x1="601.19" y1="-758.6" x2="587.86" y2="-741.9" gradientTransform="matrix(0.5, 0, 0, -0.5, -276, -342)" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#e25a01"/><stop offset="1" stop-color="#fab01c"/></linearGradient></defs><path d="M14,28.75H34.09a7.91,7.91,0,1,0,0-15.81h-.51a10.79,10.79,0,0,0-20.12,2.88A6.47,6.47,0,0,0,14,28.75" fill="#e7f1ff" fill-rule="evenodd"/><path d="M14,28.75H34.09a7.91,7.91,0,1,0,0-15.81h-.51a10.79,10.79,0,0,0-20.12,2.88A6.47,6.47,0,0,0,14,28.75" fill-rule="evenodd" fill="url(#a)"/><path d="M14,28.75H34.09a7.91,7.91,0,1,0,0-15.81h-.51a10.79,10.79,0,0,0-20.12,2.88A6.47,6.47,0,0,0,14,28.75" fill-rule="evenodd" fill="url(#b)"/><path d="M7.5,22.28A6.47,6.47,0,0,1,14,15.81h2.15a8.63,8.63,0,0,1,8.63,8.63v4.31H14A6.47,6.47,0,0,1,7.5,22.28" fill="url(#c)"/><path d="M13.25,18A10.78,10.78,0,1,1,24,28.75,10.78,10.78,0,0,1,13.25,18" fill="url(#d)"/><circle cx="34.09" cy="20.84" r="7.91" fill="url(#e)"/><path d="M21,34.85h8.13a6.88,6.88,0,0,0,0-13.76l-.45,0a9.38,9.38,0,0,0-17.5,2.5,5.63,5.63,0,0,0,.45,11.24Z" fill="#fff" fill-rule="evenodd"/><path d="M21,34.85h8.13a6.88,6.88,0,0,0,0-13.76l-.45,0a9.38,9.38,0,0,0-17.5,2.5,5.63,5.63,0,0,0,.45,11.24Z" fill-rule="evenodd" fill="url(#f)"/><path d="M6,29.22a5.63,5.63,0,0,1,5.63-5.63H13.5a7.5,7.5,0,0,1,7.5,7.5v3.76H11.63A5.63,5.63,0,0,1,6,29.22" fill="url(#g)"/><path d="M11,25.47a9.38,9.38,0,1,1,9.38,9.38A9.38,9.38,0,0,1,11,25.47" fill="url(#h)"/><circle cx="29.13" cy="27.97" r="6.88" fill="url(#i)"/><path d="M15.56,32.35l6.15-9.23a.51.51,0,0,1,.93.34l-.79,7.09h2.66a.52.52,0,0,1,.43.81l-6.15,9.23a.51.51,0,0,1-.93-.34l.79-7.09H16a.52.52,0,0,1-.52-.52.5.5,0,0,1,.09-.29" fill-rule="evenodd" fill="url(#j)"/><path d="M15.56,32.35l6.15-9.23a.51.51,0,0,1,.93.34l-.79,7.09h2.66a.52.52,0,0,1,.43.81l-6.15,9.23a.51.51,0,0,1-.93-.34l.79-7.09H16a.52.52,0,0,1-.52-.52.5.5,0,0,1,.09-.29" fill-rule="evenodd" fill="url(#k)"/></svg>"""

SVG_THUNDERSTORM_NIGHT = SVG_THUNDERSTORM_DAY

SVG_DEFAULT = SVG_SUNNY_DAY


# Maps icon key names to SVG strings
ICON_MAP: dict[str, str] = {
    "sunnyDay": SVG_SUNNY_DAY,
    "clearNight": SVG_CLEAR_NIGHT,
    "cloudyDay": SVG_CLOUDY_DAY,
    "cloudyNight": SVG_CLOUDY_NIGHT,
    "foggyDay": SVG_FOGGY_DAY,
    "foggyNight": SVG_FOGGY_NIGHT,
    "drizzleDay": SVG_DRIZZLE_DAY,
    "drizzleNight": SVG_DRIZZLE_NIGHT,
    "rainyDay": SVG_RAINY_DAY,
    "rainyNight": SVG_RAINY_NIGHT,
    "snowyDay": SVG_SNOWY_DAY,
    "snowyNight": SVG_SNOWY_NIGHT,
    "thunderstormDay": SVG_THUNDERSTORM_DAY,
    "thunderstormNight": SVG_THUNDERSTORM_NIGHT,
    "default": SVG_DEFAULT,
}


def get_weather_icon(code: int, is_day: bool) -> tuple[str, str, str]:
    """Map a WMO weather code to an SVG icon, CSS class name, and description.

    Args:
        code: WMO weather interpretation code (0-99).
        is_day: True for daytime, False for nighttime.

    Returns:
        Tuple of (svg_string, icon_class_name, description_text).
    """
    time = "Day" if is_day else "Night"

    # Clear sky
    if code == 0:
        if is_day:
            return ICON_MAP["sunnyDay"], "sunnyDay", "Clear sky"
        return ICON_MAP["clearNight"], "clearNight", "Clear sky"

    # Mainly clear, Partly cloudy, Overcast
    if code in {1, 2, 3}:
        key = f"cloudy{time}"
        descriptions = {1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}
        return ICON_MAP[key], key, descriptions.get(code, "Cloudy")

    # Fog
    if code in {45, 48}:
        key = f"foggy{time}"
        desc = "Fog" if code == 45 else "Depositing rime fog"
        return ICON_MAP[key], key, desc

    # Drizzle
    if code in {51, 53, 55, 56, 57}:
        key = f"drizzle{time}"
        descriptions = {
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Drizzle")

    # Rain
    if code in {61, 63, 65, 66, 67}:
        key = f"rainy{time}"
        descriptions = {
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Rain")

    # Snow
    if code in {71, 73, 75, 77}:
        key = f"snowy{time}"
        descriptions = {
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Snow")

    # Rain showers
    if code in {80, 81, 82}:
        key = f"rainy{time}"
        descriptions = {
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Rain showers")

    # Snow showers
    if code in {85, 86}:
        key = f"snowy{time}"
        desc = "Slight snow showers" if code == 85 else "Heavy snow showers"
        return ICON_MAP[key], key, desc

    # Thunderstorm
    if code in {95, 96, 99}:
        key = f"thunderstorm{time}"
        descriptions = {
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Thunderstorm")

    # Default fallback
    return ICON_MAP["default"], "default", "Unknown"
