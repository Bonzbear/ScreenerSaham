import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np

TOKEN = "8639573881:AAHQfo4YEqjFVMMurZD4-gS416UrMbukGsE"
CHAT_ID = "-1003724967633"

MAX_SCORE = 1000

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def format_telegram(df):
    no = 0
    if df.empty:
        return "Tidak ada sinyal hari ini"

    indonesia_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(indonesia_tz).strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n"
    msg += "━━━━━━━━━━━━━━\n"

    for _, row in df.head(5).iterrows():
        warning = row["Warning"] if "Warning" in df.columns else ""
        if warning:
            ticker = f"{row['Ticker'].replace('.JK','')} {warning}"
        else:
            ticker = row["Ticker"].replace(".JK", "")

        no += 1
        msg += f"<b>{no}. {ticker}</b>\n"

    msg += (
        "\n<b>⚠️ Menandakan saham dengan risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\n"
        "Pre-closing (bid 3-5 tick di atas IEP)\n\n"
        "<b>🎯 Target</b>\n"
        "TP fleksibel (bisa >1% / ARA)\n\n"
        "<b>🛑 Risiko</b>\n"
        "CL jika bertahan di bawah support hingga penutupan\n\n"
        "<b>ℹ️ Disclaimer</b>\n"
        "Bukan rekomendasi investasi. Lakukan analisa mandiri.\n"
    )
    return msg


# =========================
# GET ALL IDX TICKERS (MANUAL LIST)
# =========================
@st.cache_data(ttl=600) # Cache 1 hari (24 jam)
def get_all_active_tickers():
    """Menggunakan daftar saham manual. Tambahkan saham baru di dalam list ini."""
    tickers = [
        'AALI.JK', 'ABBA.JK', 'ABDA.JK', 'ABMM.JK', 'ACES.JK', 'ACST.JK', 'ADES.JK', 'ADHI.JK', 'AISA.JK', 'AKKU.JK', 
        'AKPI.JK', 'AKRA.JK', 'AKSI.JK', 'ALDO.JK', 'ALKA.JK', 'ALMI.JK', 'ALTO.JK', 'AMAG.JK', 'AMFG.JK', 'AMIN.JK', 
        'AMRT.JK', 'ANJT.JK', 'ANTM.JK', 'APEX.JK', 'APIC.JK', 'APII.JK', 'APLI.JK', 'APLN.JK', 'ARGO.JK', 'ARII.JK', 
        'ARNA.JK', 'ARTA.JK', 'ARTI.JK', 'ARTO.JK', 'ASBI.JK', 'ASDM.JK', 'ASGR.JK', 'ASII.JK', 'ASJT.JK', 'ASMI.JK', 
        'ASRI.JK', 'ASRM.JK', 'ASSA.JK', 'ATIC.JK', 'AUTO.JK', 'BABP.JK', 'BACA.JK', 'BAJA.JK', 'BALI.JK', 'BAPA.JK', 
        'BATA.JK', 'BAYU.JK', 'BBCA.JK', 'BBHI.JK', 'BBKP.JK', 'BBLD.JK', 'BBMD.JK', 'BBNI.JK', 'BBRI.JK', 'BBRM.JK', 
        'BBTN.JK', 'BBYB.JK', 'BCAP.JK', 'BCIC.JK', 'BCIP.JK', 'BDMN.JK', 'BEKS.JK', 'BEST.JK', 'BFIN.JK', 'BGTG.JK', 
        'BHIT.JK', 'BIKA.JK', 'BIMA.JK', 'BINA.JK', 'BIPI.JK', 'BIPP.JK', 'BIRD.JK', 'BISI.JK', 'BJBR.JK', 'BJTM.JK', 
        'BKDP.JK', 'BKSL.JK', 'BKSW.JK', 'BLTA.JK', 'BLTZ.JK', 'BMAS.JK', 'BMRI.JK', 'BMSR.JK', 'BMTR.JK', 'BNBA.JK', 
        'BNBR.JK', 'BNGA.JK', 'BNII.JK', 'BNLI.JK', 'BOLT.JK', 'BPFI.JK', 'BPII.JK', 'BRAM.JK', 'BRMS.JK', 'BRNA.JK', 
        'BRPT.JK', 'BSDE.JK', 'BSIM.JK', 'BSSR.JK', 'BSWD.JK', 'BTEK.JK', 'BTEL.JK', 'BTON.JK', 'BTPN.JK', 'BUDI.JK', 
        'BUKK.JK', 'BULL.JK', 'BUMI.JK', 'BUVA.JK', 'BVIC.JK', 'BWPT.JK', 'BYAN.JK', 'CANI.JK', 'CASS.JK', 'CEKA.JK', 
        'CENT.JK', 'CFIN.JK', 'CINT.JK', 'CITA.JK', 'CLPI.JK', 'CMNP.JK', 'CMPP.JK', 'CNKO.JK', 'CNTX.JK', 'COWL.JK', 
        'CPIN.JK', 'CPRO.JK', 'CSAP.JK', 'CTBN.JK', 'CTRA.JK', 'CTTH.JK', 'DART.JK', 'DEFI.JK', 'DEWA.JK', 'DGIK.JK', 
        'DILD.JK', 'DKFT.JK', 'DLTA.JK', 'DMAS.JK', 'DNAR.JK', 'DNET.JK', 'DOID.JK', 'DPNS.JK', 'DSFI.JK', 'DSNG.JK', 
        'DSSA.JK', 'DUTI.JK', 'DVLA.JK', 'DYAN.JK', 'ECII.JK', 'EKAD.JK', 'ELSA.JK', 'ELTY.JK', 'EMDE.JK', 'EMTK.JK', 
        'ENRG.JK', 'EPMT.JK', 'ERAA.JK', 'ERTX.JK', 'ESSA.JK', 'ESTI.JK', 'ETWA.JK', 'EXCL.JK', 'FAST.JK', 'FASW.JK', 
        'FISH.JK', 'FMII.JK', 'FORU.JK', 'FPNI.JK', 'GAMA.JK', 'GDST.JK', 'GDYR.JK', 'GEMA.JK', 'GEMS.JK', 'GGRM.JK', 
        'GIAA.JK', 'GJTL.JK', 'GLOB.JK', 'GMTD.JK', 'GOLD.JK', 'GOLL.JK', 'GPRA.JK', 'GSMF.JK', 'GTBO.JK', 'GWSA.JK', 
        'GZCO.JK', 'HADE.JK', 'HDFA.JK', 'HERO.JK', 'HEXA.JK', 'HITS.JK', 'HMSP.JK', 'HOME.JK', 'HOTL.JK', 'HRUM.JK', 
        'IATA.JK', 'IBFN.JK', 'IBST.JK', 'ICBP.JK', 'ICON.JK', 'IGAR.JK', 'IIKP.JK', 'IKAI.JK', 'IKBI.JK', 'IMAS.JK', 
        'IMJS.JK', 'IMPC.JK', 'INAF.JK', 'INAI.JK', 'INCI.JK', 'INCO.JK', 'INDF.JK', 'INDR.JK', 'INDS.JK', 'INDX.JK', 
        'INDY.JK', 'INKP.JK', 'INPC.JK', 'INPP.JK', 'INRU.JK', 'INTA.JK', 'INTD.JK', 'INTP.JK', 'IPOL.JK', 'ISAT.JK', 
        'ISSP.JK', 'ITMA.JK', 'ITMG.JK', 'JAWA.JK', 'JECC.JK', 'JIHD.JK', 'JKON.JK', 'JPFA.JK', 'JRPT.JK', 'JSMR.JK', 
        'JSPT.JK', 'JTPE.JK', 'KAEF.JK', 'KARW.JK', 'KBLI.JK', 'KBLM.JK', 'KBLV.JK', 'KBRI.JK', 'KDSI.JK', 'KIAS.JK', 
        'KICI.JK', 'KIJA.JK', 'KKGI.JK', 'KLBF.JK', 'KOBX.JK', 'KOIN.JK', 'KONI.JK', 'KOPI.JK', 'KPIG.JK', 'KRAS.JK', 
        'KREN.JK', 'LAPD.JK', 'LCGP.JK', 'LEAD.JK', 'LINK.JK', 'LION.JK', 'LMAS.JK', 'LMPI.JK', 'LMSH.JK', 'LPCK.JK', 
        'LPGI.JK', 'LPIN.JK', 'LPKR.JK', 'LPLI.JK', 'LPPF.JK', 'LPPS.JK', 'LRNA.JK', 'LSIP.JK', 'LTLS.JK', 'MAGP.JK', 
        'MAIN.JK', 'MAPI.JK', 'MAYA.JK', 'MBAP.JK', 'MBSS.JK', 'MBTO.JK', 'MCOR.JK', 'MDIA.JK', 'MDKA.JK', 'MDLN.JK', 
        'MDRN.JK', 'MEDC.JK', 'MEGA.JK', 'MERK.JK', 'META.JK', 'MFMI.JK', 'MGNA.JK', 'MICE.JK', 'MIDI.JK', 'MIKA.JK', 
        'MIRA.JK', 'MITI.JK', 'MKPI.JK', 'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 'MMLP.JK', 'MNCN.JK', 'MPMX.JK', 
        'MPPA.JK', 'MRAT.JK', 'MREI.JK', 'MSKY.JK', 'MTDL.JK', 'MTFN.JK', 'MTLA.JK', 'MTSM.JK', 'MYOH.JK', 'MYOR.JK', 
        'MYTX.JK', 'NELY.JK', 'NIKL.JK', 'NIRO.JK', 'NISP.JK', 'NOBU.JK', 'NRCA.JK', 'OCAP.JK', 'OKAS.JK', 'OMRE.JK', 
        'PADI.JK', 'PALM.JK', 'PANR.JK', 'PANS.JK', 'PBRX.JK', 'PDES.JK', 'PEGE.JK', 'PGAS.JK', 'PGLI.JK', 'PICO.JK', 
        'PJAA.JK', 'PKPK.JK', 'PLAS.JK', 'PLIN.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK', 'PNLF.JK', 'PSAB.JK', 'PSDN.JK', 
        'PSKT.JK', 'PTBA.JK', 'PTIS.JK', 'PTPP.JK', 'PTRO.JK', 'PTSN.JK', 'PTSP.JK', 'PUDP.JK', 'PWON.JK', 'PYFA.JK', 
        'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RIMO.JK', 'RODA.JK', 
        'ROTI.JK', 'RUIS.JK', 'SAFE.JK', 'SAME.JK', 'SCCO.JK', 'SCMA.JK', 'SCPI.JK', 'SDMU.JK', 'SDPC.JK', 'SDRA.JK', 
        'SGRO.JK', 'SHID.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK', 'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKYB.JK', 
        'SMAR.JK', 'SMBR.JK', 'SMCB.JK', 'SMDM.JK', 'SMDR.JK', 'SMGR.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK', 'SMRU.JK', 
        'SMSM.JK', 'SOCI.JK', 'SONA.JK', 'SPMA.JK', 'SQMI.JK', 'SRAJ.JK', 'SRIL.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 
        'SSMS.JK', 'SSTM.JK', 'STAR.JK', 'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'TALF.JK', 'TARA.JK', 'TAXI.JK', 
        'TBIG.JK', 'TBLA.JK', 'TBMS.JK', 'TCID.JK', 'TELE.JK', 'TFCO.JK', 'TGKA.JK', 'TIFA.JK', 'TINS.JK', 'TIRA.JK', 
        'TIRT.JK', 'TKIM.JK', 'TLKM.JK', 'TMAS.JK', 'TMPO.JK', 'TOBA.JK', 'TOTL.JK', 'TOTO.JK', 'TOWR.JK', 'TPIA.JK', 
        'TPMA.JK', 'TRAM.JK', 'TRIL.JK', 'TRIM.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK', 'TRUS.JK', 'TSPC.JK', 'ULTJ.JK', 
        'UNIC.JK', 'UNIT.JK', 'UNSP.JK', 'UNTR.JK', 'UNVR.JK', 'VICO.JK', 'VINS.JK', 'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 
        'WAPO.JK', 'WEHA.JK', 'WICO.JK', 'WIIM.JK', 'WIKA.JK', 'WINS.JK', 'WOMF.JK', 'WSKT.JK', 'WTON.JK', 'YPAS.JK', 
        'YULE.JK', 'ZBRA.JK', 'SHIP.JK', 'CASA.JK', 'DAYA.JK', 'DPUM.JK', 'IDPR.JK', 'JGLE.JK', 'KINO.JK', 'MARI.JK', 
        'MKNT.JK', 'MTRA.JK', 'OASA.JK', 'POWR.JK', 'INCF.JK', 'WSBP.JK', 'PBSA.JK', 'PRDA.JK', 'BOGA.JK', 'BRIS.JK', 
        'PORT.JK', 'CARS.JK', 'MINA.JK', 'CLEO.JK', 'TAMU.JK', 'CSIS.JK', 'TGRA.JK', 'FIRE.JK', 'TOPS.JK', 'KMTR.JK', 
        'ARMY.JK', 'MAPB.JK', 'WOOD.JK', 'HRTA.JK', 'MABA.JK', 'HOKI.JK', 'MPOW.JK', 'MARK.JK', 'NASA.JK', 'MDKI.JK', 
        'BELL.JK', 'KIOS.JK', 'GMFI.JK', 'MTWI.JK', 'ZINC.JK', 'MCAS.JK', 'PPRE.JK', 'WEGE.JK', 'PSSI.JK', 'MORA.JK', 
        'DWGL.JK', 'PBID.JK', 'JMAS.JK', 'CAMP.JK', 'IPCM.JK', 'PCAR.JK', 'LCKM.JK', 'BOSS.JK', 'HELI.JK', 'JSKY.JK', 
        'INPS.JK', 'GHON.JK', 'TDPM.JK', 'DFAM.JK', 'NICK.JK', 'BTPS.JK', 'SPTO.JK', 'PRIM.JK', 'HEAL.JK', 'TRUK.JK', 
        'PZZA.JK', 'TUGU.JK', 'MSIN.JK', 'SWAT.JK', 'TNCA.JK', 'MAPA.JK', 'TCPI.JK', 'IPCC.JK', 'RISE.JK', 'BPTR.JK', 
        'POLL.JK', 'NFCX.JK', 'MGRO.JK', 'NUSA.JK', 'FILM.JK', 'ANDI.JK', 'LAND.JK', 'MOLI.JK', 'PANI.JK', 'DIGI.JK', 
        'CITY.JK', 'SAPX.JK', 'SURE.JK', 'HKMU.JK', 'MPRO.JK', 'DUCK.JK', 'GOOD.JK', 'SKRN.JK', 'YELO.JK', 'CAKK.JK', 
        'SATU.JK', 'SOSS.JK', 'DEAL.JK', 'POLA.JK', 'DIVA.JK', 'LUCK.JK', 'URBN.JK', 'SOTS.JK', 'ZONE.JK', 'PEHA.JK', 
        'FOOD.JK', 'BEEF.JK', 'POLI.JK', 'CLAY.JK', 'NATO.JK', 'JAYA.JK', 'COCO.JK', 'MTPS.JK', 'CPRI.JK', 'HRME.JK', 
        'POSA.JK', 'JAST.JK', 'FITT.JK', 'BOLA.JK', 'CCSI.JK', 'SFAN.JK', 'POLU.JK', 'KJEN.JK', 'KAYU.JK', 'ITIC.JK', 
        'PAMG.JK', 'IPTV.JK', 'BLUE.JK', 'ENVY.JK', 'EAST.JK', 'LIFE.JK', 'FUJI.JK', 'KOTA.JK', 'INOV.JK', 'ARKA.JK', 
        'SMKL.JK', 'HDIT.JK', 'KEEN.JK', 'BAPI.JK', 'TFAS.JK', 'GGRP.JK', 'OPMS.JK', 'NZIA.JK', 'SLIS.JK', 'PURE.JK', 
        'IRRA.JK', 'DMMX.JK', 'SINI.JK', 'WOWS.JK', 'ESIP.JK', 'TEBE.JK', 'KEJU.JK', 'PSGO.JK', 'AGAR.JK', 'IFSH.JK', 
        'REAL.JK', 'IFII.JK', 'PMJS.JK', 'UCID.JK', 'GLVA.JK', 'PGJO.JK', 'AMAR.JK', 'CSRA.JK', 'INDO.JK', 'AMOR.JK', 
        'TRIN.JK', 'DMND.JK', 'PURA.JK', 'PTPW.JK', 'TAMA.JK', 'IKAN.JK', 'SAMF.JK', 'SBAT.JK', 'KBAG.JK', 'CBMF.JK', 
        'RONY.JK', 'CSMI.JK', 'BBSS.JK', 'BHAT.JK', 'CASH.JK', 'TECH.JK', 'EPAC.JK', 'UANG.JK', 'PGUN.JK', 'SOFA.JK', 
        'PPGL.JK', 'TOYS.JK', 'SGER.JK', 'TRJA.JK', 'PNGO.JK', 'SCNP.JK', 'BBSI.JK', 'KMDS.JK', 'PURI.JK', 'SOHO.JK', 
        'HOMI.JK', 'ROCK.JK', 'ENZO.JK', 'PLAN.JK', 'PTDU.JK', 'ATAP.JK', 'VICI.JK', 'PMMP.JK', 'BANK.JK', 'WMUU.JK', 
        'EDGE.JK', 'UNIQ.JK', 'BEBS.JK', 'SNLK.JK', 'ZYRX.JK', 'LFLO.JK', 'FIMP.JK', 'TAPG.JK', 'NPGF.JK', 'LUCY.JK', 
        'ADCP.JK', 'HOPE.JK', 'MGLV.JK', 'TRUE.JK', 'LABA.JK', 'ARCI.JK', 'IPAC.JK', 'MASB.JK', 'BMHS.JK', 'FLMC.JK', 
        'NICL.JK', 'UVCR.JK', 'BUKA.JK', 'HAIS.JK', 'OILS.JK', 'GPSO.JK', 'MCOL.JK', 'RSGK.JK', 'RUNS.JK', 'SBMA.JK', 
        'CMNT.JK', 'GTSI.JK', 'IDEA.JK', 'KUAS.JK', 'BOBA.JK', 'MTEL.JK', 'DEPO.JK', 'BINO.JK', 'CMRY.JK', 'WGSH.JK', 
        'TAYS.JK', 'WMPP.JK', 'RMKE.JK', 'OBMD.JK', 'AVIA.JK', 'IPPE.JK', 'NASI.JK', 'BSML.JK', 'DRMA.JK', 'ADMR.JK', 
        'SEMA.JK', 'ASLC.JK', 'NETV.JK', 'BAUT.JK', 'ENAK.JK', 'NTBK.JK', 'SMKM.JK', 'STAA.JK', 'NANO.JK', 'BIKE.JK', 
        'WIRG.JK', 'SICO.JK', 'GOTO.JK', 'TLDN.JK', 'MTMH.JK', 'WINR.JK', 'IBOS.JK', 'OLIV.JK', 'ASHA.JK', 'SWID.JK', 
        'TRGU.JK', 'ARKO.JK', 'CHEM.JK', 'DEWI.JK', 'AXIO.JK', 'KRYA.JK', 'HATM.JK', 'RCCC.JK', 'GULA.JK', 'JARR.JK', 
        'AMMS.JK', 'RAFI.JK', 'KKES.JK', 'ELPI.JK', 'EURO.JK', 'KLIN.JK', 'TOOL.JK', 'BUAH.JK', 'CRAB.JK', 'MEDS.JK', 
        'COAL.JK', 'PRAY.JK', 'CBUT.JK', 'BELI.JK', 'MKTR.JK', 'OMED.JK', 'BSBK.JK', 'PDPP.JK', 'KDTN.JK', 'ZATA.JK', 
        'NINE.JK', 'MMIX.JK', 'PADA.JK', 'ISAP.JK', 'VTNY.JK', 'SOUL.JK', 'ELIT.JK', 'BEER.JK', 'CBPE.JK', 'SUNI.JK', 
        'CBRE.JK', 'WINE.JK', 'BMBL.JK', 'PEVE.JK', 'LAJU.JK', 'FWCT.JK', 'NAYZ.JK', 'IRSX.JK', 'PACK.JK', 'VAST.JK', 
        'CHIP.JK', 'HALO.JK', 'KING.JK', 'PGEO.JK', 'FUTR.JK', 'HILL.JK', 'BDKR.JK', 'PTMP.JK', 'SAGE.JK', 'TRON.JK', 
        'CUAN.JK', 'NSSS.JK', 'GTRA.JK', 'HAJJ.JK', 'JATI.JK', 'TYRE.JK', 'MPXL.JK', 'SMIL.JK', 'KLAS.JK', 'MAXI.JK', 
        'VKTR.JK', 'RELF.JK', 'AMMN.JK', 'CRSN.JK', 'GRPM.JK', 'WIDI.JK', 'TGUK.JK', 'INET.JK', 'MAHA.JK', 'RMKO.JK', 
        'CNMA.JK', 'FOLK.JK', 'HBAT.JK', 'GRIA.JK', 'PPRI.JK', 'ERAL.JK', 'CYBR.JK', 'MUTU.JK', 'LMAX.JK', 'HUMI.JK', 
        'MSIE.JK', 'RSCH.JK', 'BABY.JK', 'AEGS.JK', 'IOTF.JK', 'KOCI.JK', 'PTPS.JK', 'BREN.JK', 'STRK.JK', 'KOKA.JK', 
        'LOPI.JK', 'UDNG.JK', 'RGAS.JK', 'MSTI.JK', 'IKPM.JK', 'AYAM.JK', 'SURI.JK', 'ASLI.JK', 'GRPH.JK', 'SMGA.JK', 
        'UNTD.JK', 'TOSK.JK', 'MPIX.JK', 'ALII.JK', 'MKAP.JK', 'MEJA.JK', 'LIVE.JK', 'HYGN.JK', 'BAIK.JK', 'VISI.JK', 
        'AREA.JK', 'MHKI.JK', 'ATLA.JK', 'DATA.JK', 'SOLA.JK', 'BATR.JK', 'SPRE.JK', 'PART.JK', 'GOLF.JK', 'ISEA.JK', 
        'BLES.JK', 'GUNA.JK', 'LABS.JK', 'DOSS.JK', 'NEST.JK', 'PTMR.JK', 'VERN.JK', 'DAAZ.JK', 'BOAT.JK', 'NAIK.JK', 
        'AADI.JK', 'MDIY.JK', 'KSIX.JK', 'RATU.JK', 'YOII.JK', 'HGII.JK', 'BRRC.JK', 'DGWG.JK', 'CBDK.JK', 'OBAT.JK', 
        'MINE.JK', 'ASPR.JK', 'PSAT.JK', 'COIN.JK', 'CDIA.JK', 'BLOG.JK', 'MERI.JK', 'CHEK.JK', 'PMUI.JK', 'EMAS.JK', 
        'PJHB.JK', 'RLCO.JK', 'SUPA.JK', 'KAQI.JK', 'YUPI.JK', 'FORE.JK', 'MDLA.JK', 'DKHH.JK', 'AYLS.JK', 'DADA.JK', 
        'ASPI.JK', 'ESTA.JK', 'BESS.JK', 'AMAN.JK', 'CARE.JK', 'PIPA.JK', 'NCKL.JK', 'MENN.JK', 'AWAN.JK', 'MBMA.JK', 
        'RAAM.JK', 'DOOH.JK', 'CGAS.JK', 'NICE.JK', 'MSJA.JK', 'SMLE.JK', 'ACRO.JK', 'MANG.JK', 'WIFI.JK', 'FAPA.JK', 
        'DCII.JK', 'KETR.JK', 'DGNS.JK', 'UFOE.JK', 'ADMF.JK', 'ADMG.JK', 'ADRO.JK', 'AGII.JK', 'AGRO.JK', 'AGRS.JK', 
        'AHAP.JK', 'AIMS.JK', 'PNSE.JK', 'POLY.JK', 'POOL.JK', 'PPRO.JK'
    ]
    # Hapus duplikat untuk jaga-jaga
    return list(set(tickers))


# =========================
# YAHOO FINANCE DATA
# =========================
@st.cache_data(ttl=600) # Cache 1 jam agar run selanjutnya instan
def get_yahoo_data(tickers):
    combined = {}
    chunk_size = 150 # Batching agar request API Yahoo Finance tidak ditolak
    
    # Progress Bar untuk UI
    progress_text = "Mengunduh histori harga..."
    my_bar = st.progress(0, text=progress_text)
    
    total_chunks = (len(tickers) // chunk_size) + 1
    
    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        
        # Update progress bar
        percent_complete = int(((idx + 1) / total_chunks) * 100)
        my_bar.progress(percent_complete if percent_complete <= 100 else 100, 
                        text=f"Mendownload data saham batch {idx+1}/{total_chunks} dari Yahoo Finance...")

        data = yf.download(
            tickers=chunk,
            period="3y",
            group_by="ticker",
            progress=False,
            auto_adjust=False,
            threads=True
        )
        
        if len(chunk) == 1:
            ticker = chunk[0]
            df = data.copy()
            df = df.dropna(subset=["Open", "Close", "Volume"])
            if not df.empty:
                df.index = pd.to_datetime(df.index).normalize()
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                combined[ticker] = df
        else:
            for ticker in chunk:
                if ticker in data.columns.levels[0]:
                    df = data[ticker].copy()
                    df = df.dropna(subset=["Open", "Close", "Volume"])
                    if not df.empty:
                        df.index = pd.to_datetime(df.index).normalize()
                        if df.index.tz is not None:
                            df.index = df.index.tz_localize(None)
                        combined[ticker] = df
                        
    my_bar.empty() # Hilangkan progress bar setelah selesai
    return combined


# =========================
# PREPARE
# =========================
def prepare_data(df):
    df = df.sort_index()

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    df = df[df["Volume"] > 0]
    
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()
    df["Value"] = df["Close"] * df["Volume"]
    df["AvgValue20"] = df["Value"].rolling(20).mean()
    df["ValueRatio"] = df["Value"] / df["AvgValue20"]

    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()

    df = df.dropna(
        subset=[
            "SMA5",
            "VOLMA20",
            "VOLMA5",
            "AvgValue20",
            "VWAP"
        ]
    )

    return df

# =========================
# ARA
# =========================
def get_ara_limit(price):
    if price < 200:
        return 0.35
    elif price <= 5000:
        return 0.25
    else:
        return 0.20


# =========================
# SIGNAL
# =========================
# =========================
# SIGNAL (Buy On Open Momentum)
# =========================
def is_signal(df, i):
    today = df.iloc[i]
    prev = df.iloc[i-1]
    
    open_ = today["Open"]
    high = today["High"]
    close = today["Close"]
    volume = today["Volume"]

    prev_close = prev["Close"]

    sma5 = today["SMA5"]
    avg_value = today["AvgValue20"]
    avg_volume = today["VOLMA20"]

    change_pct = (close - prev_close) / prev_close
    ara = get_ara_limit(prev_close)

    # 1. Filter Harga (Hindari saham gocap murni atau saham terlalu mahal)
    if close > 6500 or close < 50:
        return False

    # 2. Filter ARA (Hindari saham yang ditutup ARA kaku, rawan profit taking besok pagi)
    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.33:
        return False

    # 3. Filter Likuiditas (Wajib likuid agar bisa Auto Sell besok paginya)
    # Transaksi rata-rata 20 hari wajib > Rp 10 Miliar
    if avg_value < 10_000_000_000:
        return False

    # ==============================================================
    # 4. KRITERIA KUNCI: STRATEGI BUY ON OPEN (MOMENTUM CLOSING)
    # ==============================================================
    
    # A. Tren & Posisi (Harus hijau dan di atas MA5)
    if close <= open_ or close <= prev_close or close <= sma5:
        return False

    # B. Volume Spike (Volume hari ini WAJIB lebih besar 1.5x dari rata-rata 20 hari)
    # Ini menandakan ada akumulasi besar-besaran sebelum pasar tutup
    if volume < (avg_volume * 1.5):
        return False
        
    # C. Close = High (Nyaris Marubozu) - INI YANG PALING PENTING
    # Jarak dari Close ke High maksimal 1% (Buntut atas sangat pendek/tidak ada)
    # Jika buntut atas panjang, artinya buyer gagal mempertahankan harga di pucuk.
    upper_wick_pct = (high - close) / close
    if upper_wick_pct > 0.01: # Toleransi buntut atas max 1%
        return False
        
    # D. Body Candle Cukup Signifikan
    # Kenaikan (Body) hari ini minimal 2%. Hindari candle doji/tipis yang volumenya besar (rawan distribusi).
    body_pct = (close - open_) / open_
    if body_pct < 0.02:
        return False

    return True


# =========================
# SCORE
# =========================
def calculate_score(df):
    today = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = today["Open"]
    high = today["High"]
    low = today["Low"]
    close = today["Close"]

    score = 0
    warning = ""

    if prev["Close"] < prev["SMA5"]: score += 125
    if today["Volume"] > today["VOLMA20"]: score += 125
    if today["Volume"] > today["VOLMA5"]: score += 125
    if today["Low"] > prev["Low"]: score += 125
    if today["High"] > prev["High"]: score += 125
    if (open_ - low) > (high - close): score += 125
    if today["Close"] > today["VWAP"]: score += 125
    if prev["Close"] < prev["VWAP"]: score += 125

    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    if body > 0 and upper_wick > body * 1.5:
        score -= 100
        warning = "⚠️"

    return score, warning


# =========================
# BACKTEST + EV
# =========================
# =========================
# BACKTEST + EV (Buy on Open Logic)
# =========================
def backtest_ev(df):
    returns = []

    for i in range(20, len(df)-1):
        if not is_signal(df, i):
            continue

        next_day = df.iloc[i+1]

        # Karena strategi Anda Beli di OPEN besok paginya:
        open_next = next_day["Open"]
        high_next = next_day["High"]

        # Hindari error bagi nol jika open_next = 0 (data corrupt)
        if open_next == 0:
            continue

        # Hitung untung dari harga BUKA (Open) ke harga TERTINGGI (High) hari itu
        ret = (high_next - open_next) / open_next
        returns.append(ret)

    total_trades = len(returns)

    if total_trades == 0:
        return 0, 0, 0

    # Hitung Winrate: Berapa kali harga High menyentuh +1.5% dari harga Buka (Open)?
    # Asumsi target 1% ++ (1.5% untuk cover fee sekuritas)
    winrate = sum(1 for r in returns if r >= 0.015) / total_trades

    # Hitung rata-rata profit
    profitable_returns = [r for r in returns if r > 0]
    if len(profitable_returns) == 0:
        ev = 0
    else:
        ev = sum(profitable_returns) / len(profitable_returns)

    return round(winrate * 100, 2), round(ev * 100, 2), total_trades
# =========================
# SCREENER
# =========================
# =========================
# SCREENER
# =========================
def run_screener(data, offset=0):
    results = []
    
    calc_bar = st.progress(0, text="Mengkalkulasi Signal & Backtest EV...")
    total_items = len(data)

    if total_items == 0:
        return pd.DataFrame()

    for idx, (ticker, df) in enumerate(data.items()):
        if idx % 50 == 0 or idx == total_items - 1:
            calc_bar.progress((idx + 1) / total_items, text=f"Menganalisis {ticker} ({idx+1}/{total_items})...")
            
        df = prepare_data(df)

        # Pastikan data cukup panjang
        if len(df) < 30 + offset:
            continue
            
        # Tentukan target hari (0 = hari ini, 1 = kemarin)
        target_idx = len(df) - 1 - offset

        # Cek sinyal pada hari target
        if not is_signal(df, target_idx):
            continue

        # Potong dataframe hanya sampai hari target untuk menghitung score 
        # (agar tidak mengintip masa depan)
        df_target = df.iloc[:target_idx+1]
        score, warning = calculate_score(df_target)
        score_pct = (score / MAX_SCORE) * 100

        # Backtest menggunakan dataframe sampai hari target
        winrate, ev, total_trades = backtest_ev(df_target)

        if total_trades < 5:
            valid_winrate = 50.0 
        else:
            valid_winrate = winrate

        probability = (score_pct * 0.3) + (valid_winrate * 0.7)

        latest = df_target.sort_index().tail(1)
        
        # --- FITUR CEK HASIL HARI INI (Jika Backtest Kemarin) ---
        cuan_hari_ini = "-"
        if offset == 1 and len(df) > target_idx + 1:
            # Mengambil data hari ini (T+1 dari hari target)
            data_besok = df.iloc[target_idx + 1]
            open_besok = data_besok["Open"]
            high_besok = data_besok["High"]
            
            if open_besok > 0:
                # Hitung lompatan tertinggi dari harga Open ke High
                potensi_profit = ((high_besok - open_besok) / open_besok) * 100
                cuan_hari_ini = f"{potensi_profit:.2f}%"
        # --------------------------------------------------------

        results.append({
            "Ticker": ticker,
            "Price": float(latest["Close"].values[0]),
            "SMA5": round(float(latest["SMA5"].values[0]), 2),
            "Warning": warning,
            "Score (%)": round(score_pct, 2),
            "Winrate (%)": winrate, 
            "Trades": total_trades, 
            "Probability (%)": round(probability, 2),
            "EV (%)": ev,
            "Cuan Maks Pagi Ini": cuan_hari_ini # Menambahkan kolom hasil
        })

    calc_bar.empty()
    df_result = pd.DataFrame(results)

    if not df_result.empty:
        df_result = df_result.sort_values(by="Probability (%)", ascending=False)
        df_result.insert(0, "Rank", range(1, len(df_result)+1))

    return df_result
    

# =========================
# UI
# =========================
# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia (Daftar Manual)")

st.markdown("""
Sistem ini mencari saham dengan momentum penutupan yang kuat (Buy on Open besoknya).
""")

# Menambahkan Pilihan Hari
mode_analisis = st.radio(
    "Pilih Waktu Analisis Sinyal:", 
    ["Sinyal Hari Ini (Live/Data Terakhir)", "Sinyal Kemarin (Cek Hasil Pagi Ini)"],
    horizontal=True
)

# Set offset berdasarkan pilihan
offset_hari = 1 if "Kemarin" in mode_analisis else 0

if st.button("▶️ Scan Seluruh Saham"):
    
    with st.spinner("Membaca daftar kode saham dari sistem..."):
        tickers = get_all_active_tickers()
        st.info(f"Berhasil memuat **{len(tickers)}** kode saham.")

    # Mengunduh Data Yahoo Finance
    data = get_yahoo_data(tickers)
    st.session_state["data"] = data
    
    # Menjalankan Screener dengan offset yang dipilih
    df = run_screener(data, offset=offset_hari)

    if df.empty:
        st.warning("Tidak ada sinyal saham yang memenuhi kriteria.")
    else:
        st.session_state["df"] = df
        st.success(f"Selesai! {len(df)} saham potensial ditemukan.")

# =========================
# DISPLAY + CHECKLIST
# =========================
if "df" in st.session_state:
    df_display = st.session_state["df"].copy()
    df_display["Kirim"] = False

    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True
    )
    st.session_state["edited_df"] = edited_df

# =========================
# TELEGRAM
# =========================
if "edited_df" in st.session_state:
    st.write("---")
    if st.button("📤 Kirim ke Telegram"):
        selected = st.session_state["edited_df"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih minimal 1 saham pada checkbox (Kirim) terlebih dahulu.")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Sinyal berhasil dikirim ke Telegram!")
