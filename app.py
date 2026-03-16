import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Screener Saham Indonesia")

menu = st.sidebar.selectbox(
    "Menu",
    ["Screener","Backtest","Winrate Analyzer"]
)

# =====================================
# LIST TICKER (ubah sesuai kebutuhan)
# =====================================

TICKERS = ['AALI.JK', 'ABBA.JK', 'ABDA.JK', 'ABMM.JK', 'ACES.JK', 'ACST.JK', 'ADES.JK', 'ADHI.JK', 'AISA.JK', 'AKKU.JK', 'AKPI.JK', 'AKRA.JK', 'AKSI.JK', 'ALDO.JK', 'ALKA.JK', 'ALMI.JK', 'ALTO.JK', 'AMAG.JK', 'AMFG.JK', 'AMIN.JK', 'AMRT.JK', 'ANJT.JK', 'ANTM.JK', 'APEX.JK', 'APIC.JK', 'APII.JK', 'APLI.JK', 'APLN.JK', 'ARGO.JK', 'ARII.JK', 'ARNA.JK', 'ARTA.JK', 'ARTI.JK', 'ARTO.JK', 'ASBI.JK', 'ASDM.JK', 'ASGR.JK', 'ASII.JK', 'ASJT.JK', 'ASMI.JK', 'ASRI.JK', 'ASRM.JK', 'ASSA.JK', 'ATIC.JK', 'AUTO.JK', 'BABP.JK', 'BACA.JK', 'BAJA.JK', 'BALI.JK', 'BAPA.JK', 'BATA.JK', 'BAYU.JK', 'BBCA.JK', 'BBHI.JK', 'BBKP.JK', 'BBLD.JK', 'BBMD.JK', 'BBNI.JK', 'BBRI.JK', 'BBRM.JK', 'BBTN.JK', 'BBYB.JK', 'BCAP.JK', 'BCIC.JK', 'BCIP.JK', 'BDMN.JK', 'BEKS.JK', 'BEST.JK', 'BFIN.JK', 'BGTG.JK', 'BHIT.JK', 'BIKA.JK', 'BIMA.JK', 'BINA.JK', 'BIPI.JK', 'BIPP.JK', 'BIRD.JK', 'BISI.JK', 'BJBR.JK', 'BJTM.JK', 'BKDP.JK', 'BKSL.JK', 'BKSW.JK', 'BLTA.JK', 'BLTZ.JK', 'BMAS.JK', 'BMRI.JK', 'BMSR.JK', 'BMTR.JK', 'BNBA.JK', 'BNBR.JK', 'BNGA.JK', 'BNII.JK', 'BNLI.JK', 'BOLT.JK', 'BPFI.JK', 'BPII.JK', 'BRAM.JK', 'BRMS.JK', 'BRNA.JK', 'BRPT.JK', 'BSDE.JK', 'BSIM.JK', 'BSSR.JK', 'BSWD.JK', 'BTEK.JK', 'BTEL.JK', 'BTON.JK', 'BTPN.JK', 'BUDI.JK', 'BUKK.JK', 'BULL.JK', 'BUMI.JK', 'BUVA.JK', 'BVIC.JK', 'BWPT.JK', 'BYAN.JK', 'CANI.JK', 'CASS.JK', 'CEKA.JK', 'CENT.JK', 'CFIN.JK', 'CINT.JK', 'CITA.JK', 'CLPI.JK', 'CMNP.JK', 'CMPP.JK', 'CNKO.JK', 'CNTX.JK', 'COWL.JK', 'CPIN.JK', 'CPRO.JK', 'CSAP.JK', 'CTBN.JK', 'CTRA.JK', 'CTTH.JK', 'DART.JK', 'DEFI.JK', 'DEWA.JK', 'DGIK.JK', 'DILD.JK', 'DKFT.JK', 'DLTA.JK', 'DMAS.JK', 'DNAR.JK', 'DNET.JK', 'DOID.JK', 'DPNS.JK', 'DSFI.JK', 'DSNG.JK', 'DSSA.JK', 'DUTI.JK', 'DVLA.JK', 'DYAN.JK', 'ECII.JK', 'EKAD.JK', 'ELSA.JK', 'ELTY.JK', 'EMDE.JK', 'EMTK.JK', 'ENRG.JK', 'EPMT.JK', 'ERAA.JK', 'ERTX.JK', 'ESSA.JK', 'ESTI.JK', 'ETWA.JK', 'EXCL.JK', 'FAST.JK', 'FASW.JK', 'FISH.JK', 'FMII.JK', 'FORU.JK', 'FPNI.JK', 'GAMA.JK', 'GDST.JK', 'GDYR.JK', 'GEMA.JK', 'GEMS.JK', 'GGRM.JK', 'GIAA.JK', 'GJTL.JK', 'GLOB.JK', 'GMTD.JK', 'GOLD.JK', 'GOLL.JK', 'GPRA.JK', 'GSMF.JK', 'GTBO.JK', 'GWSA.JK', 'GZCO.JK', 'HADE.JK', 'HDFA.JK', 'HERO.JK', 'HEXA.JK', 'HITS.JK', 'HMSP.JK', 'HOME.JK', 'HOTL.JK', 'HRUM.JK', 'IATA.JK', 'IBFN.JK', 'IBST.JK', 'ICBP.JK', 'ICON.JK', 'IGAR.JK', 'IIKP.JK', 'IKAI.JK', 'IKBI.JK', 'IMAS.JK', 'IMJS.JK', 'IMPC.JK', 'INAF.JK', 'INAI.JK', 'INCI.JK', 'INCO.JK', 'INDF.JK', 'INDR.JK', 'INDS.JK', 'INDX.JK', 'INDY.JK', 'INKP.JK', 'INPC.JK', 'INPP.JK', 'INRU.JK', 'INTA.JK', 'INTD.JK', 'INTP.JK', 'IPOL.JK', 'ISAT.JK', 'ISSP.JK', 'ITMA.JK', 'ITMG.JK', 'JAWA.JK', 'JECC.JK', 'JIHD.JK', 'JKON.JK', 'JPFA.JK', 'JRPT.JK', 'JSMR.JK', 'JSPT.JK', 'JTPE.JK', 'KAEF.JK', 'KARW.JK', 'KBLI.JK', 'KBLM.JK', 'KBLV.JK', 'KBRI.JK', 'KDSI.JK', 'KIAS.JK', 'KICI.JK', 'KIJA.JK', 'KKGI.JK', 'KLBF.JK', 'KOBX.JK', 'KOIN.JK', 'KONI.JK', 'KOPI.JK', 'KPIG.JK', 'KRAS.JK', 'KREN.JK', 'LAPD.JK', 'LCGP.JK', 'LEAD.JK', 'LINK.JK', 'LION.JK', 'LMAS.JK', 'LMPI.JK', 'LMSH.JK', 'LPCK.JK', 'LPGI.JK', 'LPIN.JK', 'LPKR.JK', 'LPLI.JK', 'LPPF.JK', 'LPPS.JK', 'LRNA.JK', 'LSIP.JK', 'LTLS.JK', 'MAGP.JK', 'MAIN.JK', 'MAPI.JK', 'MAYA.JK', 'MBAP.JK', 'MBSS.JK', 'MBTO.JK', 'MCOR.JK', 'MDIA.JK', 'MDKA.JK', 'MDLN.JK', 'MDRN.JK', 'MEDC.JK', 'MEGA.JK', 'MERK.JK', 'META.JK', 'MFMI.JK', 'MGNA.JK', 'MICE.JK', 'MIDI.JK', 'MIKA.JK', 'MIRA.JK', 'MITI.JK', 'MKPI.JK', 'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 'MMLP.JK', 'MNCN.JK', 'MPMX.JK', 'MPPA.JK', 'MRAT.JK', 'MREI.JK', 'MSKY.JK', 'MTDL.JK', 'MTFN.JK', 'MTLA.JK', 'MTSM.JK', 'MYOH.JK', 'MYOR.JK', 'MYTX.JK', 'NELY.JK', 'NIKL.JK', 'NIRO.JK', 'NISP.JK', 'NOBU.JK', 'NRCA.JK', 'OCAP.JK', 'OKAS.JK', 'OMRE.JK', 'PADI.JK', 'PALM.JK', 'PANR.JK', 'PANS.JK', 'PBRX.JK', 'PDES.JK', 'PEGE.JK', 'PGAS.JK', 'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK', 'PLAS.JK', 'PLIN.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK', 'PNLF.JK', 'PSAB.JK', 'PSDN.JK', 'PSKT.JK', 'PTBA.JK', 'PTIS.JK', 'PTPP.JK', 'PTRO.JK', 'PTSN.JK', 'PTSP.JK', 'PUDP.JK', 'PWON.JK', 'PYFA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RIMO.JK', 'RODA.JK', 'ROTI.JK', 'RUIS.JK', 'SAFE.JK', 'SAME.JK', 'SCCO.JK', 'SCMA.JK', 'SCPI.JK', 'SDMU.JK', 'SDPC.JK', 'SDRA.JK', 'SGRO.JK', 'SHID.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK', 'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKYB.JK', 'SMAR.JK', 'SMBR.JK', 'SMCB.JK', 'SMDM.JK', 'SMDR.JK', 'SMGR.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK', 'SMRU.JK', 'SMSM.JK', 'SOCI.JK', 'SONA.JK', 'SPMA.JK', 'SQMI.JK', 'SRAJ.JK', 'SRIL.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 'SSMS.JK', 'SSTM.JK', 'STAR.JK', 'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'TALF.JK', 'TARA.JK', 'TAXI.JK', 'TBIG.JK', 'TBLA.JK', 'TBMS.JK', 'TCID.JK', 'TELE.JK', 'TFCO.JK', 'TGKA.JK', 'TIFA.JK', 'TINS.JK', 'TIRA.JK', 'TIRT.JK', 'TKIM.JK', 'TLKM.JK', 'TMAS.JK', 'TMPO.JK', 'TOBA.JK', 'TOTL.JK', 'TOTO.JK', 'TOWR.JK', 'TPIA.JK', 'TPMA.JK', 'TRAM.JK', 'TRIL.JK', 'TRIM.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK', 'TRUS.JK', 'TSPC.JK', 'ULTJ.JK', 'UNIC.JK', 'UNIT.JK', 'UNSP.JK', 'UNTR.JK', 'UNVR.JK', 'VICO.JK', 'VINS.JK', 'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 'WAPO.JK', 'WEHA.JK', 'WICO.JK', 'WIIM.JK', 'WIKA.JK', 'WINS.JK', 'WOMF.JK', 'WSKT.JK', 'WTON.JK', 'YPAS.JK', 'YULE.JK', 'ZBRA.JK', 'SHIP.JK', 'CASA.JK', 'DAYA.JK', 'DPUM.JK', 'IDPR.JK', 'JGLE.JK', 'KINO.JK', 'MARI.JK', 'MKNT.JK', 'MTRA.JK', 'OASA.JK', 'POWR.JK', 'INCF.JK', 'WSBP.JK', 'PBSA.JK', 'PRDA.JK', 'BOGA.JK', 'BRIS.JK', 'PORT.JK', 'CARS.JK', 'MINA.JK', 'CLEO.JK', 'TAMU.JK', 'CSIS.JK', 'TGRA.JK', 'FIRE.JK', 'TOPS.JK', 'KMTR.JK', 'ARMY.JK', 'MAPB.JK', 'WOOD.JK', 'HRTA.JK', 'MABA.JK', 'HOKI.JK', 'MPOW.JK', 'MARK.JK', 'NASA.JK', 'MDKI.JK', 'BELL.JK', 'KIOS.JK', 'GMFI.JK', 'MTWI.JK', 'ZINC.JK', 'MCAS.JK', 'PPRE.JK', 'WEGE.JK', 'PSSI.JK', 'MORA.JK', 'DWGL.JK', 'PBID.JK', 'JMAS.JK', 'CAMP.JK', 'IPCM.JK', 'PCAR.JK', 'LCKM.JK', 'BOSS.JK', 'HELI.JK', 'JSKY.JK', 'INPS.JK', 'GHON.JK', 'TDPM.JK', 'DFAM.JK', 'NICK.JK', 'BTPS.JK', 'SPTO.JK', 'PRIM.JK', 'HEAL.JK', 'TRUK.JK', 'PZZA.JK', 'TUGU.JK', 'MSIN.JK', 'SWAT.JK', 'TNCA.JK', 'MAPA.JK', 'TCPI.JK', 'IPCC.JK', 'RISE.JK', 'BPTR.JK', 'POLL.JK', 'NFCX.JK', 'MGRO.JK', 'NUSA.JK', 'FILM.JK', 'ANDI.JK', 'LAND.JK', 'MOLI.JK', 'PANI.JK', 'DIGI.JK', 'CITY.JK', 'SAPX.JK', 'SURE.JK', 'HKMU.JK', 'MPRO.JK', 'DUCK.JK', 'GOOD.JK', 'SKRN.JK', 'YELO.JK', 'CAKK.JK', 'SATU.JK', 'SOSS.JK', 'DEAL.JK', 'POLA.JK', 'DIVA.JK', 'LUCK.JK', 'URBN.JK', 'SOTS.JK', 'ZONE.JK', 'PEHA.JK', 'FOOD.JK', 'BEEF.JK', 'POLI.JK', 'CLAY.JK', 'NATO.JK', 'JAYA.JK', 'COCO.JK', 'MTPS.JK', 'CPRI.JK', 'HRME.JK', 'POSA.JK', 'JAST.JK', 'FITT.JK', 'BOLA.JK', 'CCSI.JK', 'SFAN.JK', 'POLU.JK', 'KJEN.JK', 'KAYU.JK', 'ITIC.JK', 'PAMG.JK', 'IPTV.JK', 'BLUE.JK', 'ENVY.JK', 'EAST.JK', 'LIFE.JK', 'FUJI.JK', 'KOTA.JK', 'INOV.JK', 'ARKA.JK', 'SMKL.JK', 'HDIT.JK', 'KEEN.JK', 'BAPI.JK', 'TFAS.JK', 'GGRP.JK', 'OPMS.JK', 'NZIA.JK', 'SLIS.JK', 'PURE.JK', 'IRRA.JK', 'DMMX.JK', 'SINI.JK', 'WOWS.JK', 'ESIP.JK', 'TEBE.JK', 'KEJU.JK', 'PSGO.JK', 'AGAR.JK', 'IFSH.JK', 'REAL.JK', 'IFII.JK', 'PMJS.JK', 'UCID.JK', 'GLVA.JK', 'PGJO.JK', 'AMAR.JK', 'CSRA.JK', 'INDO.JK', 'AMOR.JK', 'TRIN.JK', 'DMND.JK', 'PURA.JK', 'PTPW.JK', 'TAMA.JK', 'IKAN.JK', 'SAMF.JK', 'SBAT.JK', 'KBAG.JK', 'CBMF.JK', 'RONY.JK', 'CSMI.JK', 'BBSS.JK', 'BHAT.JK', 'CASH.JK', 'TECH.JK', 'EPAC.JK', 'UANG.JK', 'PGUN.JK', 'SOFA.JK', 'PPGL.JK', 'TOYS.JK', 'SGER.JK', 'TRJA.JK', 'PNGO.JK', 'SCNP.JK', 'BBSI.JK', 'KMDS.JK', 'PURI.JK', 'SOHO.JK', 'HOMI.JK', 'ROCK.JK', 'ENZO.JK', 'PLAN.JK', 'PTDU.JK', 'ATAP.JK', 'VICI.JK', 'PMMP.JK', 'BANK.JK', 'WMUU.JK', 'EDGE.JK', 'UNIQ.JK', 'BEBS.JK', 'SNLK.JK', 'ZYRX.JK', 'LFLO.JK', 'FIMP.JK', 'TAPG.JK', 'NPGF.JK', 'LUCY.JK', 'ADCP.JK', 'HOPE.JK', 'MGLV.JK', 'TRUE.JK', 'LABA.JK', 'ARCI.JK', 'IPAC.JK', 'MASB.JK', 'BMHS.JK', 'FLMC.JK', 'NICL.JK', 'UVCR.JK', 'BUKA.JK', 'HAIS.JK', 'OILS.JK', 'GPSO.JK', 'MCOL.JK', 'RSGK.JK', 'RUNS.JK', 'SBMA.JK', 'CMNT.JK', 'GTSI.JK', 'IDEA.JK', 'KUAS.JK', 'BOBA.JK', 'MTEL.JK', 'DEPO.JK', 'BINO.JK', 'CMRY.JK', 'WGSH.JK', 'TAYS.JK', 'WMPP.JK', 'RMKE.JK', 'OBMD.JK', 'AVIA.JK', 'IPPE.JK', 'NASI.JK', 'BSML.JK', 'DRMA.JK', 'ADMR.JK', 'SEMA.JK', 'ASLC.JK', 'NETV.JK', 'BAUT.JK', 'ENAK.JK', 'NTBK.JK', 'SMKM.JK', 'STAA.JK', 'NANO.JK', 'BIKE.JK', 'WIRG.JK', 'SICO.JK', 'GOTO.JK', 'TLDN.JK', 'MTMH.JK', 'WINR.JK', 'IBOS.JK', 'OLIV.JK', 'ASHA.JK', 'SWID.JK', 'TRGU.JK', 'ARKO.JK', 'CHEM.JK', 'DEWI.JK', 'AXIO.JK', 'KRYA.JK', 'HATM.JK', 'RCCC.JK', 'GULA.JK', 'JARR.JK', 'AMMS.JK', 'RAFI.JK', 'KKES.JK', 'ELPI.JK', 'EURO.JK', 'KLIN.JK', 'TOOL.JK', 'BUAH.JK', 'CRAB.JK', 'MEDS.JK', 'COAL.JK', 'PRAY.JK', 'CBUT.JK', 'BELI.JK', 'MKTR.JK', 'OMED.JK', 'BSBK.JK', 'PDPP.JK', 'KDTN.JK', 'ZATA.JK', 'NINE.JK', 'MMIX.JK', 'PADA.JK', 'ISAP.JK', 'VTNY.JK', 'SOUL.JK', 'ELIT.JK', 'BEER.JK', 'CBPE.JK', 'SUNI.JK', 'CBRE.JK', 'WINE.JK', 'BMBL.JK', 'PEVE.JK', 'LAJU.JK', 'FWCT.JK', 'NAYZ.JK', 'IRSX.JK', 'PACK.JK', 'VAST.JK', 'CHIP.JK', 'HALO.JK', 'KING.JK', 'PGEO.JK', 'FUTR.JK', 'HILL.JK', 'BDKR.JK', 'PTMP.JK', 'SAGE.JK', 'TRON.JK', 'CUAN.JK', 'NSSS.JK', 'GTRA.JK', 'HAJJ.JK', 'JATI.JK', 'TYRE.JK', 'MPXL.JK', 'SMIL.JK', 'KLAS.JK', 'MAXI.JK', 'VKTR.JK', 'RELF.JK', 'AMMN.JK', 'CRSN.JK', 'GRPM.JK', 'WIDI.JK', 'TGUK.JK', 'INET.JK', 'MAHA.JK', 'RMKO.JK', 'CNMA.JK', 'FOLK.JK', 'HBAT.JK', 'GRIA.JK', 'PPRI.JK', 'ERAL.JK', 'CYBR.JK', 'MUTU.JK', 'LMAX.JK', 'HUMI.JK', 'MSIE.JK', 'RSCH.JK', 'BABY.JK', 'AEGS.JK', 'IOTF.JK', 'KOCI.JK', 'PTPS.JK', 'BREN.JK', 'STRK.JK', 'KOKA.JK', 'LOPI.JK', 'UDNG.JK', 'RGAS.JK', 'MSTI.JK', 'IKPM.JK', 'AYAM.JK', 'SURI.JK', 'ASLI.JK', 'GRPH.JK', 'SMGA.JK', 'UNTD.JK', 'TOSK.JK', 'MPIX.JK', 'ALII.JK', 'MKAP.JK', 'MEJA.JK', 'LIVE.JK', 'HYGN.JK', 'BAIK.JK', 'VISI.JK', 'AREA.JK', 'MHKI.JK', 'ATLA.JK', 'DATA.JK', 'SOLA.JK', 'BATR.JK', 'SPRE.JK', 'PART.JK', 'GOLF.JK', 'ISEA.JK', 'BLES.JK', 'GUNA.JK', 'LABS.JK', 'DOSS.JK', 'NEST.JK', 'PTMR.JK', 'VERN.JK', 'DAAZ.JK', 'BOAT.JK', 'NAIK.JK', 'AADI.JK', 'MDIY.JK', 'KSIX.JK', 'RATU.JK', 'YOII.JK', 'HGII.JK', 'BRRC.JK', 'DGWG.JK', 'CBDK.JK', 'OBAT.JK', 'MINE.JK', 'ASPR.JK', 'PSAT.JK', 'COIN.JK', 'CDIA.JK', 'BLOG.JK', 'MERI.JK', 'CHEK.JK', 'PMUI.JK', 'EMAS.JK', 'PJHB.JK', 'RLCO.JK', 'SUPA.JK', 'KAQI.JK', 'YUPI.JK', 'FORE.JK', 'MDLA.JK', 'DKHH.JK', 'AYLS.JK', 'DADA.JK', 'ASPI.JK', 'ESTA.JK', 'BESS.JK', 'AMAN.JK', 'CARE.JK', 'PIPA.JK', 'NCKL.JK', 'MENN.JK', 'AWAN.JK', 'MBMA.JK', 'RAAM.JK', 'DOOH.JK', 'CGAS.JK', 'NICE.JK', 'MSJA.JK', 'SMLE.JK', 'ACRO.JK', 'MANG.JK', 'WIFI.JK', 'FAPA.JK', 'DCII.JK', 'KETR.JK', 'DGNS.JK', 'UFOE.JK', 'ADMF.JK', 'ADMG.JK', 'ADRO.JK', 'AGII.JK', 'AGRO.JK', 'AGRS.JK', 'AHAP.JK', 'AIMS.JK', 'PNSE.JK', 'POLY.JK', 'POOL.JK', 'PPRO.JK']

# =====================================
# FUNCTION SCREENER
# =====================================

def run_screener():

    hasil=[]

    for ticker in TICKERS:

        df=yf.download(ticker,period="60d",progress=False)

        if df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()

        df=df.dropna()

        today=df.iloc[-1]
        prev=df.iloc[-2]

        close=float(today["Close"])
        prev_close=float(prev["Close"])

        volume=float(today["Volume"])
        prev_volume=float(prev["Volume"])

        sma5=float(today["SMA5"])

        value=close*volume

        signal=(
            volume>prev_volume and
            prev_close<close and
            close>sma5 and
            value>5000000000
        )

        if signal:

            hasil.append({
                "Ticker":ticker,
                "Close":round(close,2),
                "Volume":int(volume),
                "Value":int(value)
            })

    return pd.DataFrame(hasil)

# =====================================
# FUNCTION BACKTEST
# =====================================

def run_backtest(ticker):

    ticker=ticker.upper()+".JK"

    df=yf.download(ticker,period="2y",progress=False)

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    df["SMA5"]=df["Close"].rolling(5).mean()

    df=df.dropna().reset_index()

    hasil=[]

    for i in range(5,len(df)-1):

        today=df.iloc[i]
        prev=df.iloc[i-1]
        tomorrow=df.iloc[i+1]

        close=float(today["Close"])
        prev_close=float(prev["Close"])

        volume=float(today["Volume"])
        prev_volume=float(prev["Volume"])

        sma5=float(today["SMA5"])

        value=close*volume

        signal=(
            volume>prev_volume and
            prev_close<close and
            close>sma5 and
            value>5000000000
        )

        if not signal:
            continue

        gain=(tomorrow["High"]-close)/close*100

        hasil.append({
            "Date":today["Date"],
            "Next High %":round(gain,2)
        })

    return pd.DataFrame(hasil)

# =====================================
# FUNCTION WINRATE ANALYZER
# =====================================

def run_winrate_analyzer(tickers):

    results=[]

    for ticker in tickers:

        df=yf.download(ticker,period="2y",progress=False)

        if df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()
        df["SMA20"]=df["Close"].rolling(20).mean()
        df["VolMA20"]=df["Volume"].rolling(20).mean()

        df=df.dropna().reset_index()

        for i in range(20,len(df)-1):

            today=df.iloc[i]
            prev=df.iloc[i-1]
            tomorrow=df.iloc[i+1]

            close=today["Close"]
            prev_close=prev["Close"]

            volume=today["Volume"]
            prev_volume=prev["Volume"]

            value=close*volume

            signal=(
                volume>prev_volume and
                prev_close<close and
                close>today["SMA5"] and
                value>5000000000
            )

            if not signal:
                continue

            gain=(tomorrow["High"]-close)/close*100

            results.append({

                "ticker":ticker,
                "gain":gain,
                "trend":close>today["SMA20"],
                "breakout":close>prev["High"],
                "volume_spike":volume>today["VolMA20"],
                "range":today["High"]/today["Low"]>1.03

            })

    df=pd.DataFrame(results)

    return df

# =====================================
# MENU SCREENER
# =====================================

if menu=="Screener":

    st.header("Screener Saham")

    if st.button("Run Screener"):

        df=run_screener()

        if df.empty:
            st.write("Tidak ada saham memenuhi kriteria")
        else:
            st.dataframe(df)

# =====================================
# MENU BACKTEST
# =====================================

if menu=="Backtest":

    st.header("Backtest")

    ticker_input=st.text_input("Ticker","BBRI")

    if st.button("Run Backtest"):

        df=run_backtest(ticker_input)

        if df.empty:
            st.write("Tidak ada sinyal")
        else:

            st.dataframe(df)

            total=len(df)

            tp1=(df["Next High %"]>=1).sum()
            tp2=(df["Next High %"]>=2).sum()

            st.write("Total Signal:",total)
            st.write("TP1 Hit:",tp1)
            st.write("TP2 Hit:",tp2)

# =====================================
# MENU WINRATE ANALYZER
# =====================================

if menu=="Winrate Analyzer":

    st.header("Analisa Winrate dari Screener")

    ticker_input=st.text_input(
        "Masukkan ticker hasil screener",
        "BBRI,ADRO,PTBA"
    )

    if st.button("Analyze"):

        tickers=[x.strip().upper()+".JK" for x in ticker_input.split(",")]

        df=run_winrate_analyzer(tickers)

        if df.empty:

            st.write("Tidak ada data")

        else:

            filters=["trend","breakout","volume_spike","range"]

            hasil=[]

            for f in filters:

                subset=df[df[f]]

                if len(subset)>0:

                    win=(subset["gain"]>=1).sum()

                    winrate=win/len(subset)*100

                    hasil.append({
                        "Filter":f,
                        "Signals":len(subset),
                        "Winrate TP1 %":round(winrate,2)
                    })

            result_df=pd.DataFrame(hasil)

            st.dataframe(result_df)
