import logging

# Our imports
import emission.core.get_database as edb
import emission.analysis.modelling.tour_model.cluster_pipeline as pipeline
import emission.analysis.modelling.tour_model.similarity as similarity
import emission.analysis.modelling.tour_model.featurization as featurization
import emission.analysis.modelling.tour_model.representatives as representatives
import emission.storage.decorations.analysis_timeseries_queries as esda
import pandas as pd
from numpy import *
from sklearn import metrics
from pandas.testing import assert_frame_equal

# Spanish words to English
span_eng_dict = {'revisado_bike':'test ride with bike','placas_de carro':'car plates','aseguranza':'insurance',
 'iglesia':'church','curso':'course','mi_hija recién aliviada':'my daughter just had a new baby',
 'servicio_comunitario':'community service','pago_de aseguranza':'insurance payment',
 'grupo_comunitario':'community group','caminata_comunitaria':'community walk'}

# Convert purpose
map_pur_dict = {'course':'school','work_- lunch break':'lunch_break','on_the way home':'home',
               'insurance_payment':'insurance'}

# precision_bins takes five parameters
# - all_bins_preci: the list that collects precision of each bin, should pass in an empty list
# - sp2en=None means no need to translate language
#   sp2en='True' will use span_eng_dict to change Spanish to English
#
# - cvt_purpose=None means no need to convert purposes
#   cvt_purpose='True' will use map_pur_dict to convert purposes
#   using this parameter should also set sp2en='True'
def precision_bins (all_bins_preci,bins,non_empty_trips,sp2en=None,cvt_purpose=None):
    for bin in bins:
        bin_user_input = (non_empty_trips[i].data["user_input"] for i in bin if
                          non_empty_trips[i].data["user_input"] != {})
        bin_df = pd.DataFrame(data=bin_user_input)
        if sp2en == 'True':
            bin_df = bin_df.replace(span_eng_dict)
        if cvt_purpose == 'True':
            bin_df = bin_df.replace(map_pur_dict)
        duplic_trips = bin_df[bin_df.duplicated(keep=False)]

        # for bin that doesn't have duplicate trips, assign 0 as precision
        if duplic_trips.empty and len(bin_df) > 1:
            all_bins_preci.append(0)
        # for bin only has one trip, assign 1.0 as precision
        elif len(bin_df) == 1:
            all_bins_preci.append(1.0)
        else:
            duplic = duplic_trips.groupby(duplic_trips.columns.tolist()).apply(lambda x: tuple(x.index)).tolist()
            max_duplic = max(duplic, key=lambda i: len(i))
            precision = round(len(max_duplic) / len(bin), 2)
            all_bins_preci.append(precision)
    return all_bins_preci


# precision_all_users takes four parameters
# - all_users: pass in all participants' data
# - sp2en: default None, no need to change language
# - cvt_purpose: default None, no need to convert purpose
def precision_bin_all_users(all_users,radius,sp2en=None,cvt_purpose=None):
    all_users_preci = []
    for i in range(len(all_users)):
        user = all_users[i]
        trips = pipeline.read_data(uuid=user, key=esda.CONFIRMED_TRIP_KEY)
        all_bins_preci = []
        non_empty_trips = [t for t in trips if t["data"]["user_input"] != {}]
        if non_empty_trips != {}:
            sim = similarity.similarity(non_empty_trips, radius)
            if sim.data:
                sim.bin_data()
                all_bins_preci = precision_bins(all_bins_preci, sim.bins, non_empty_trips, sp2en, cvt_purpose)
        all_users_preci.append(round(mean(all_bins_preci), 2))
    return all_users_preci


# v_measure_bins takes 5 parameters
# - sp2en=True: change Spanish to English
# - cvt_pur_mo=True: convert purposes and replaced mode
# - cutoff=True: choose to analyze bins above cutoff
# - cutoff=None: analyze all bins
# Note: for sp2en and cvt_pur_mo, set either one to be True as needed. cvt_pur_mo will change language first
def v_measure_bins(all_users,radius,sp2en=None,cvt_pur_mo=None,cutoff=None):
    homo_score = []
    comp_score = []
    v_score = []
    for i in range(len(all_users)):
        user = all_users[i]
        trips = pipeline.read_data(uuid=user, key=esda.CONFIRMED_TRIP_KEY)
        non_empty_trips = [t for t in trips if t["data"]["user_input"] != {}]
        valid_trips = [t for t in non_empty_trips if 'mode_confirm' in t["data"]["user_input"] and
                       'purpose_confirm' in t["data"]["user_input"] and 'replaced_mode' in t["data"]["user_input"]]
        sim = similarity.similarity(valid_trips, radius)
        filter_trips = sim.data

        # filter out users that haven't enough trips (at least 10) to analyze
        if len(filter_trips) < 10:
            homo_score.append(NaN)
            comp_score.append(NaN)
            v_score.append(NaN)
            continue
        sim.bin_data()
        if cutoff is None:
            trip_index_ls = []
            bins = sim.bins
            for bin in bins:
                for index in bin:
                    trip_index_ls.append(index)
            bin_trips = [filter_trips[num] for num in trip_index_ls]

        elif cutoff:
            sim.delete_bins()
            bin_trips = sim.newdata
            bins = sim.bins

            if len(bin_trips) < 10:
                homo_score.append(NaN)
                comp_score.append(NaN)
                v_score.append(NaN)
                continue
        bin_trips_df = pd.DataFrame(data=[trip["data"]["user_input"] for trip in bin_trips])

        if sp2en:
            bin_trips_df = bin_trips_df.replace(span_eng_dict)
        elif cvt_pur_mo:
            bin_trips_df = bin_trips_df.replace(span_eng_dict)
            bin_trips_df = bin_trips_df.replace(map_pur_dict)
            for a in range(len(bin_trips_df)):
                if bin_trips_df.iloc[a]["replaced_mode"] == "same_mode":
                    # to see which row will be converted
                    logging.debug("The following rows will be changed: %s", bin_trips_df.iloc[a])
                    bin_trips_df.iloc[a]["replaced_mode"] = bin_trips_df.iloc[a]['mode_confirm']

        # turn all user_input into list without binning
        bin_trips_user_input_ls = bin_trips_df.values.tolist()
        # drop duplicate user_input
        no_dup_df = bin_trips_df.drop_duplicates()
        # turn non-duplicate user_input into list
        no_dup_list = no_dup_df.values.tolist()

        # collect labels_true based on user_input
        labels_true = []
        for trip in bin_trips_user_input_ls:
            if trip in no_dup_list:
                labels_true.append(no_dup_list.index(trip))

        # collect labels_pred based on bins
        labels_pred = []
        for b in range(len(bins)):
            for trip in bins[b]:
                labels_pred.append(b)

        # compare the trips order in bins and those in valid_trips using timestamp
        bin_trips_ts = pd.DataFrame(data=[trip["data"]["start_ts"] for trip in bin_trips])
        bin_ls = []
        for bin in bins:
            for index in bin:
                bin_ls.append(index)
        bins_ts = pd.DataFrame(data=[filter_trips[i]["data"]["start_ts"] for i in bin_ls])
        # compare two data frames, return nothing if two data frames are the same
        assert_frame_equal(bins_ts, bin_trips_ts)
        homo = metrics.homogeneity_score(labels_true, labels_pred)
        homo_score.append(float('%.3f' % homo))
        comp = metrics.completeness_score(labels_true, labels_pred)
        comp_score.append(float('%.3f' % comp))
        v = metrics.v_measure_score(labels_true, labels_pred)
        v_score.append(float('%.3f' % v))

    return homo_score, comp_score, v_score


# - sp2en=True: change Spanish to English
# - cvt_pur_mo=True: convert purposes and replaced mode
# - cutoff=True: choose to analyze bins above cutoff
# - cutoff=None: analyze all bins
# Note: for sp2en and cvt_pur_mo, set either one to be True as needed. cvt_pur_mo will change language first
def v_measure_clusters(all_users,radius,sp2en=None,cvt_pur_mo=None):
    homo_score = []
    comp_score = []
    v_score = []
    for i in range(len(all_users)):
        user = all_users[i]
        trips = pipeline.read_data(uuid=user, key=esda.CONFIRMED_TRIP_KEY)
        non_empty_trips = [t for t in trips if t["data"]["user_input"] != {}]
        valid_trips = [t for t in non_empty_trips if 'mode_confirm' in t["data"]["user_input"] and
                       'purpose_confirm' in t["data"]["user_input"] and 'replaced_mode' in t["data"]["user_input"]]
        sim = similarity.similarity(valid_trips, radius)
        filter_trips = sim.data
        # filter out users that haven't enough trips (at least 10) to analyze
        if len(filter_trips) < 10:
            homo_score.append(NaN)
            comp_score.append(NaN)
            v_score.append(NaN)
            continue
        sim.bin_data()
        sim.delete_bins()
        bin_trips = sim.newdata
        bins = sim.bins

        if len(bin_trips) < 10:
            homo_score.append(NaN)
            comp_score.append(NaN)
            v_score.append(NaN)
            continue

        # clustering the data only based on sil score (min_cluster = 0) instead of bins number (len(bins))
        feat = featurization.featurization(bin_trips)
        min = 0
        max = int(math.ceil(1.5 * len(bins)))
        feat.cluster(min_clusters=min, max_clusters=max)
        cluster_trips = feat.data
        cluster_user_input_df = pd.DataFrame(data=[i["data"]["user_input"] for i in cluster_trips])
        if sp2en:
            # change language
            cluster_user_input_df = cluster_user_input_df.replace(span_eng_dict)
            cluster_user_input_ls = cluster_user_input_df.values.tolist()
        elif cvt_pur_mo:
            # change language first
            cluster_user_input_df = cluster_user_input_df.replace(span_eng_dict)
            # convert purpose
            cluster_user_input_df = cluster_user_input_df.replace(map_pur_dict)
            # convert mode
            for a in range(len(cluster_user_input_df)):
                if cluster_user_input_df.iloc[a]["replaced_mode"] == "same_mode":
                    cluster_user_input_df.iloc[a]["replaced_mode"] = cluster_user_input_df.iloc[a]['mode_confirm']
        # turn cluster_trips to list without any changes
        cluster_user_input_ls = cluster_user_input_df.values.tolist()
        # drop duplicate user_input
        no_dup_df = cluster_user_input_df.drop_duplicates()
        # turn non-duplicate user_input into list
        no_dup_list = no_dup_df.values.tolist()
        # collect labels_true based on user_input
        labels_true = []
        for trip in cluster_user_input_ls:
            if trip in no_dup_list:
                labels_true.append(no_dup_list.index(trip))
        labels_pred = feat.labels

        # compare the points in cluster_trips and those in feat.points, return nothing if two data frames are the same
        cluster_ps = []
        for trip in cluster_trips:
            cluster_ps.append([trip["data"]["start_loc"]["coordinates"][0],
                               trip["data"]["start_loc"]["coordinates"][1],
                               trip["data"]["end_loc"]["coordinates"][0],
                               trip["data"]["end_loc"]["coordinates"][1]])
        cluster_ps_df = pd.DataFrame(data=cluster_ps)
        label_ps_df = pd.DataFrame(data=feat.points)
        assert_frame_equal(cluster_ps_df, label_ps_df)

        homo = metrics.homogeneity_score(labels_true, labels_pred)
        homo_score.append(float('%.3f' % homo))
        comp = metrics.completeness_score(labels_true, labels_pred)
        comp_score.append(float('%.3f' % comp))
        v = metrics.v_measure_score(labels_true, labels_pred)
        v_score.append(float('%.3f' % v))

    return homo_score, comp_score, v_score



















