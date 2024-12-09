import logging
from eventmanager import Evt
from Results import RaceClassRankMethod
import RHUtils
from eventmanager import Evt
from RHRace import StartBehavior
from Results import RaceClassRankMethod
from RHUI import UIField, UIFieldType, UIFieldSelectOption

logger = logging.getLogger(__name__)

def pilot_in_leaderboard(leaderboard, pilot_id):
    return any(pilot['pilot_id'] == pilot_id for pilot in leaderboard)

def best_consecutive_laps(lap_times, x, first_Lap = 1 ):
    if len(lap_times) < x+ first_Lap:
        return None  # Not enough laps to calculate

    best_sum = float('inf')  # Start with a large number
    best_index = -1
    if (first_Lap == 1):
        lap_times = lap_times[1:]
    # Calculate the sum of `x` consecutive laps
    for i in range(len(lap_times) - x + 1):
        current_sum = sum(lap_times[i:i+x])
        if current_sum < best_sum:
            best_sum = current_sum
            best_index = i

    # Return the best sum and the laps contributing to it
    return best_sum, lap_times[best_index:best_index+x]
def filter_shortest_consecutives(data):
    pilot_best_runs = {}

    for line in data:
        pilot_id = line['pilot_id']

        # Skip pilots with laps <= 3
        if line['laps'] <= 3:
            continue

        # Parse consecutives_raw to compare numeric values
        consecutives_time = line['consecutives_raw']

        # Update pilot_best_runs if:
        # - Pilot is not already in the dict
        # - Current run has a shorter consecutives time
        if pilot_id not in pilot_best_runs or consecutives_time < pilot_best_runs[pilot_id]['consecutives_raw']:
            pilot_best_runs[pilot_id] = line

    return list(pilot_best_runs.values())

def rank_best_laps_HC(rhapi, race_class, args):
    heats = rhapi.db.heats_by_class(race_class.id)

    leaderboard = []

    for heat in heats:
        heat_result = rhapi.db.heat_results(heat)
        if heat_result:
            heat_leaderboard = heat_result[heat_result['meta']['primary_leaderboard']]
            for line in heat_leaderboard:
                if not pilot_in_leaderboard(leaderboard, line['pilot_id']):
                # Hole Handicap-Wert
                    handicap_value = rhapi.db.pilot_attribute_value(line['pilot_id'], 'Handicap')
                    try:
                        handicap = float(handicap_value.replace(',', '.')) if handicap_value else 1.0
                    except ValueError:
                        logger.warning("Handicap-Value Error Pilot %s: %s. default value 1.0 will be used.", line['pilot_id'], handicap_value)
                        handicap = 1.0
                    if line['consecutives_base'] == 3:   
                        leaderboard.append({'pilot_id': line['pilot_id'],
                                            'callsign': line['callsign'],
                                            'consecutives': line['consecutives'],
                                            'consecutives_raw': line['consecutives_raw'],
                                            'consecutives_inSec': line['consecutives_raw']*0.001,
                                            'handicap': handicap,
                                            'consecutives_raw_hc': line['consecutives_raw']*handicap,
                                            'consecutives_hc': rhapi.utils.format_time_to_str(line['consecutives_raw']*handicap)}
                                            )


                for pilot in leaderboard:
                    if pilot['pilot_id'] == line['pilot_id'] and line['consecutives_base'] == 3 and line['consecutives_raw']<pilot['consecutives_raw']:
                        pilot['consecutives']= line['consecutives']
                        pilot['consecutives_raw']= line['consecutives_raw']
                        pilot['consecutives_inSec']= line['consecutives_raw']*0.001
                        pilot['consecutives_raw_hc']= line['consecutives_raw']*pilot['handicap']
                        pilot['consecutives_hc']= rhapi.utils.format_time_to_str(line['consecutives_raw']*pilot['handicap'])

    leaderboard = sorted(
        (pilot for pilot in leaderboard if pilot['consecutives_raw_hc'] is not None),
        key=lambda pilot: pilot['consecutives_raw_hc'],
        reverse=False
    )

                        
    meta = {
    'method_label': F"Best 3 Consecutive Laps with Handicap",   
    'rank_fields': [{
        'name': 'consecutives',
        'label': "Consecutive"
    },{
        'name': 'handicap',
        'label': "Handicap"
    },{
        'name': 'consecutives_hc',
        'label': "Consecutive with Handicap"
    },{
        'name': 'consecutives_inSec',
        'label': "Consecutive in Sec"
    }]
    }
    return leaderboard, meta

def register_handlers(args):
    args['register_fn'](
        RaceClassRankMethod(
            "Best 3 Laps with Handicap",
            rank_best_laps_HC,
            {
                'laps': 3
            }
        )
    )


# Initialisierung des Handicaps als Pilotenattribut
def initialize(rhapi):
    # Pilot attributes
    handicap = UIField(name='Handicap', label='Handicap', field_type=UIFieldType.TEXT, placeholder="1,0")
    rhapi.fields.register_pilot_attribute(handicap)
    rhapi.events.on(Evt.CLASS_RANK_INITIALIZE, register_handlers)

# Funktion zur Berechnung des Rankings mit Handicap
