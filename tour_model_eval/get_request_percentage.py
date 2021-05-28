import label_processing as label_pro


# This function is to compare a trip with a group of trips to see if they happened in a same day
def match_day(trip,bin,filter_trips):
    if bin:
        t = filter_trips[bin[0]]
        if trip['data']['start_local_dt']['year']==t['data']['start_local_dt']['year']\
                and trip['data']['start_local_dt']['month']==t['data']['start_local_dt']['month']\
                and trip['data']['start_local_dt']['day']==t['data']['start_local_dt']['day']:
            return True
    return False


# This function is to compare a trip with a group of trips to see if they happened in a same month
def match_month(trip,bin,filter_trips):
    if bin:
        t = filter_trips[bin[0]]
        if trip['data']['start_local_dt']['year']==t['data']['start_local_dt']['year']\
                and trip['data']['start_local_dt']['month']==t['data']['start_local_dt']['month']:
            return True
    return False


# This function bins trips according to ['start_local_dt']
def bin_date(trip_ls,filter_trips,day=None,month=None):
    bin_date = []
    for trip_index in trip_ls:
        added = False
        trip = filter_trips[trip_index]

        for bin in bin_date:
            if day:
                if match_day(trip,bin,filter_trips):
                    bin.append(trip_index)
                    added = True
                    break
            if month:
                if match_month(trip,bin,filter_trips):
                    bin.append(trip_index)
                    added = True
                    break

        if not added:
            bin_date.append([trip_index])

    return bin_date


def find_first_trip(filter_trips,bin):
    trip_ts = [filter_trips[trip_idx]['data']["start_ts"] for trip_idx in bin]
    # - early_idx_in_bin: the earliest trip position in the bin
    early_idx_in_bin = trip_ts.index(min(trip_ts))
    # - early_trip_index: the original index of the earliest trip
    early_trip_index = bin[early_idx_in_bin]
    return early_trip_index, early_idx_in_bin


# collect requested trips and common trips(no need to request) indices above cutoff
def requested_trips_ab_cutoff(new_bins, filter_trips):
    # collect requested trip indices above cutoff
    ab_trip_ls = []
    # collect common trip indices above cutoff
    no_req_trip_ls = []
    for bin in new_bins:
        early_trip_index, early_idx_in_bin = find_first_trip(filter_trips, bin)
        ab_trip_ls.append(early_trip_index)

        # The following loop collects the original indices of the rest of the trips in the bin. Since they are not the
        # earliest one, we don't need to request for user labels
        for k in range(len(bin)):
            if k != early_idx_in_bin:
                # - no_req_trip_idx: the original index of the trip that is not requested for user labels
                no_req_trip_idx = bin[k]
                no_req_trip_ls.append(no_req_trip_idx)
    return ab_trip_ls, no_req_trip_ls


# collect requested trips indices below cutoff
def requested_trips_bl_cutoff(sim):
    # bins below cutoff
    bl_bins = sim.below_cutoff

    # collect requested trips indices below cutoff
    # effectively, bl_trip_ls = flatten(bl_bins)
    # >>> bl_bins = [[1,2],[3,4],[5,6]]
    # >>> bl_trip_ls = [item for sublist in bl_bins for item in sublist]
    # >>> bl_trip_ls
    # [1, 2, 3, 4, 5, 6]
    # the reason for flattening: add here the reason why you want to flatten the list
    bl_trip_ls = [item for sublist in bl_bins for item in sublist]
    return bl_trip_ls


# a list of all requested trips indices
def get_requested_trips(new_bins,filter_trips,sim):
    ab_trip_ls,no_req_trip_ls = requested_trips_ab_cutoff(new_bins,filter_trips)
    bl_trip_ls = requested_trips_bl_cutoff(sim)
    req_trips_ls=ab_trip_ls+bl_trip_ls
    return req_trips_ls


# get request percentage based on the number of requested trips and the total number of trips
def get_req_pct(new_labels,track,filter_trips,sim):
    # - new_bins: bins with original indices of similar trips from common trips
    # - new_label: For the first round, new_label is the copy of the first round labels, e.g. [1,1,1,2,2,2].
    # For the second round, new_label is that the first round label concatenate the second round label.
    # e.g.the label from the second round is [1,2,1,2,3,3], new_label will turn to [11,12,11,22,23,23]
    # - track: at this point, each item in the track contains the original index of a trip,
    # and the latest label of it. e.g. [ori_idx, latest_label]
    # concretely, please look at "group_similar_trips" function in label_processing.py
    # If new_label is [11,12,11,22,23,23] and the original indices of the trips is [1,2,3,4,5,6],
    # new_bins will be [[1,3],[2],[4],[5,6]]
    new_bins = label_pro.group_similar_trips(new_labels,track)
    req_trips = get_requested_trips(new_bins,filter_trips,sim)
    pct = len(req_trips)/len(filter_trips)
    return pct
