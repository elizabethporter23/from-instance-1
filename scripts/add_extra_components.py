# SPDX-FileCopyrightText: : 2017-2020 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

# coding: utf-8
"""
Adds extra extendable components to the clustered and simplified network.

Relevant Settings
-----------------

.. code:: yaml

    costs:
        year:
        USD2013_to_EUR2013:
        dicountrate:
        emission_prices:

    electricity:
        max_hours:
        marginal_cost:
        capital_cost:
        extendable_carriers:
            StorageUnit:
            Store:

.. seealso::
    Documentation of the configuration file ``config.yaml`` at :ref:`costs_cf`,
    :ref:`electricity_cf`

Inputs
------

- ``data/costs.csv``: The database of cost assumptions for all included technologies for specific years from various sources; e.g. discount rate, lifetime, investment (CAPEX), fixed operation and maintenance (FOM), variable operation and maintenance (VOM), fuel costs, efficiency, carbon-dioxide intensity.

Outputs
-------

- ``networks/elec_s{simpl}_{clusters}_ec.nc``:


Description
-----------

The rule :mod:`add_extra_components` attaches additional extendable components to the clustered and simplified network. These can be configured in the ``config.yaml`` at ``electricity: extendable_carriers:``. It processes ``networks/elec_s{simpl}_{clusters}.nc`` to build ``networks/elec_s{simpl}_{clusters}_ec.nc``, which in contrast to the former (depending on the configuration) contain with **zero** initial capacity

- ``StorageUnits`` of carrier 'H2' and/or 'battery'. If this option is chosen, every bus is given an extendable ``StorageUnit`` of the corresponding carrier. The energy and power capacities are linked through a parameter that specifies the energy capacity as maximum hours at full dispatch power and is configured in ``electricity: max_hours:``. This linkage leads to one investment variable per storage unit. The default ``max_hours`` lead to long-term hydrogen and short-term battery storage units.

- ``Stores`` of carrier 'H2' and/or 'battery' in combination with ``Links``. If this option is chosen, the script adds extra buses with corresponding carrier where energy ``Stores`` are attached and which are connected to the corresponding power buses via two links, one each for charging and discharging. This leads to three investment variables for the energy capacity, charging and discharging capacity of the storage unit.
"""
import logging
from _helpers import configure_logging

import pypsa
import pandas as pd
import numpy as np

from add_electricity import (load_costs, add_nice_carrier_names,
                             _add_missing_carriers_from_costs)

idx = pd.IndexSlice

logger = logging.getLogger(__name__)


def attach_storageunits(n, costs):
    elec_opts = snakemake.config['electricity']
    carriers = elec_opts['extendable_carriers']['StorageUnit']
    max_hours = elec_opts['max_hours']

    _add_missing_carriers_from_costs(n, costs, carriers)

    buses_i = n.buses.index

    lookup_store = {"H2": "electrolysis", "battery": "battery inverter", "gravitricity":"Gravitricity Power", "vrfb":"Flow Battery Power","ptes":"Thermal Battery Power"}
    lookup_dispatch = {"H2": "fuel cell", "battery": "battery inverter", "gravitricity":"Gravitricity Power", "vrfb":"Flow Battery Power", "ptes":"Thermal Battery Power"}

    for carrier in carriers:
        if carrier == 'gravitricity_old':
            n.madd("StorageUnit", buses_i, ' ' + carrier,
               bus=buses_i,
               carrier=carrier,
               p_nom_extendable=True,
               capital_cost=costs.at[carrier, 'capital_cost'],
               marginal_cost=costs.at[carrier, 'marginal_cost'],
               standing_loss=costs.at[carrier, 'standing_loss'],
               efficiency_store=costs.at[lookup_store[carrier], 'efficiency'],
               efficiency_dispatch=costs.at[lookup_dispatch[carrier], 'efficiency'],
               max_hours=max_hours[carrier],
               p_nom_max=4166.67,
               cyclic_state_of_charge=True)      
        else:
               n.madd("StorageUnit", buses_i, ' ' + carrier,
                     bus=buses_i,
                     carrier=carrier,
                     p_nom_extendable=True,
                     capital_cost=costs.at[carrier, 'capital_cost'],
                     marginal_cost=costs.at[carrier, 'marginal_cost'],
                     standing_loss=costs.at[carrier, 'standing_loss'],
                     efficiency_store=costs.at[lookup_store[carrier], 'efficiency'],
                     efficiency_dispatch=costs.at[lookup_dispatch[carrier], 'efficiency'],
                     max_hours=max_hours[carrier],
                     cyclic_state_of_charge=True)


def attach_stores(n, costs):
    elec_opts = snakemake.config['electricity']
    carriers = elec_opts['extendable_carriers']['Store']

    _add_missing_carriers_from_costs(n, costs, carriers)

    buses_i = n.buses.index
    bus_sub_dict = {k: n.buses[k].values for k in ['x', 'y', 'country']}

    if 'H2' in carriers:
        h2_buses_i = n.madd("Bus", buses_i + " H2", carrier="H2", **bus_sub_dict)

        n.madd("Store", h2_buses_i,
               bus=h2_buses_i,
               carrier='H2',
               e_nom_extendable=True,
               e_cyclic=True,
               capital_cost=costs.at["hydrogen storage", "capital_cost"])

        n.madd("Link", h2_buses_i + " Electrolysis",
               bus0=buses_i,
               bus1=h2_buses_i,
               carrier='H2 electrolysis',
               p_nom_extendable=True,
               efficiency=costs.at["electrolysis", "efficiency"],
               capital_cost=costs.at["electrolysis", "capital_cost"],
               marginal_cost=costs.at["electrolysis", "marginal_cost"])

        n.madd("Link", h2_buses_i + " Fuel Cell",
               bus0=h2_buses_i,
               bus1=buses_i,
               carrier='H2 fuel cell',
               p_nom_extendable=True,
               efficiency=costs.at["fuel cell", "efficiency"],
               #NB: fixed cost is per MWel
               capital_cost=costs.at["fuel cell", "capital_cost"] * costs.at["fuel cell", "efficiency"],
               marginal_cost=costs.at["fuel cell", "marginal_cost"])

    if 'battery' in carriers:
        b_buses_i = n.madd("Bus", buses_i + " battery", carrier="battery", **bus_sub_dict)

        n.madd("Store", b_buses_i,
               bus=b_buses_i,
               carrier='battery',
               e_cyclic=True,
               e_nom_extendable=True,
               capital_cost=costs.at['battery storage', 'capital_cost'],
               marginal_cost=costs.at["battery", "marginal_cost"])

        n.madd("Link", b_buses_i + " charger",
               bus0=buses_i,
               bus1=b_buses_i,
               carrier='battery charger',
               efficiency=costs.at['battery inverter', 'efficiency'],
               capital_cost=costs.at['battery inverter', 'capital_cost'],
               p_nom_extendable=True,
               marginal_cost=costs.at["battery inverter", "marginal_cost"])

        n.madd("Link", b_buses_i + " discharger",
               bus0=b_buses_i,
               bus1=buses_i,
               carrier='battery discharger',
               efficiency=costs.at['battery inverter','efficiency'],
               p_nom_extendable=True,
               marginal_cost=costs.at["battery inverter", "marginal_cost"])

    if 'gravitricity' in carriers:
        g_buses_i = n.madd("Bus", buses_i + " gravitricity", carrier="gravitricity", **bus_sub_dict)

        n.madd("Store", g_buses_i,
               bus=g_buses_i,
               carrier='gravitricity',
               e_cyclic=True,
               e_nom_extendable=True,
               capital_cost=costs.at['Gravitricity Energy', 'capital_cost'],
               marginal_cost=costs.at["gravitricity", "marginal_cost"])

        n.madd("Link", g_buses_i + " charger",
               bus0=buses_i,
               bus1=g_buses_i,
               carrier='gravitricity charger',
               efficiency=costs.at['Gravitricity Power', 'efficiency'],
               capital_cost=costs.at['Gravitricity Power', 'capital_cost'],
               p_nom_extendable=True,
               marginal_cost=costs.at["gravitricity", "marginal_cost"])

        n.madd("Link", g_buses_i + " discharger",
               bus0=g_buses_i,
               bus1=buses_i,
               carrier='gravitricity discharger',
               efficiency=costs.at['Gravitricity Power','efficiency'],
               p_nom_extendable=True,
               marginal_cost=costs.at["gravitricity", "marginal_cost"]) #assuming charger and discharger are the same

    if 'ptes' in carriers:
        t_buses_i = n.madd("Bus", buses_i + " ptes", carrier="ptes", **bus_sub_dict)

        n.madd("Store", t_buses_i,
               bus=t_buses_i,
               carrier='ptes',
               e_cyclic=True,
               e_nom_extendable=True,
               capital_cost=costs.at['Thermal Battery Energy', 'capital_cost'],
               marginal_cost=costs.at["ptes", "marginal_cost"],
               standing_loss=costs.at['Thermal Battery Energy','standing_loss'])

        n.madd("Link", t_buses_i + " charger",
               bus0=buses_i,
               bus1=t_buses_i,
               carrier='ptes charger',
               efficiency=costs.at['Thermal Battery Power', 'efficiency'],
               capital_cost=costs.at['Thermal Battery Power', 'capital_cost'],
               p_nom_extendable=True,
               marginal_cost=costs.at["ptes", "marginal_cost"])

        n.madd("Link", t_buses_i + " discharger",
               bus0=t_buses_i,
               bus1=buses_i,
               carrier='ptes discharger',
               efficiency=costs.at['Thermal Battery Power','efficiency'],
               p_nom_extendable=True,
               marginal_cost=costs.at["ptes", "marginal_cost"])

    if 'vrfb' in carriers:
        v_buses_i = n.madd("Bus", buses_i + " vrfb", carrier="vrfb", **bus_sub_dict)

        n.madd("Store", v_buses_i,
               bus=v_buses_i,
               carrier='vrfb',
               e_cyclic=True,
               e_nom_extendable=True,
               capital_cost=costs.at['Flow Battery Energy', 'capital_cost'],
               marginal_cost=costs.at["vrfb", "marginal_cost"], 
               efficiency=costs.at['Flow Battery Energy','efficiency'])

        n.madd("Link", v_buses_i + " charger",
               bus0=buses_i,
               bus1=v_buses_i,
               carrier='vrfb charger',
               efficiency=costs.at['Flow Battery Power', 'efficiency'],
               capital_cost=costs.at['Flow Battery Power', 'capital_cost'],
               p_nom_extendable=True,
               marginal_cost=costs.at["vrfb", "marginal_cost"])

        n.madd("Link", v_buses_i + " discharger",
               bus0=v_buses_i,
               bus1=buses_i,
               carrier='vrfb discharger',
               efficiency=costs.at['Flow Battery Power','efficiency'],
               p_nom_extendable=True,
               marginal_cost=costs.at["vrfb", "marginal_cost"])


def attach_hydrogen_pipelines(n, costs):
    elec_opts = snakemake.config['electricity']
    ext_carriers = elec_opts['extendable_carriers']
    as_stores = ext_carriers.get('Store', [])

    if 'H2 pipeline' not in ext_carriers.get('Link',[]): return

    assert 'H2' in as_stores, ("Attaching hydrogen pipelines requires hydrogen "
            "storage to be modelled as Store-Link-Bus combination. See "
            "`config.yaml` at `electricity: extendable_carriers: Store:`.")

    # determine bus pairs
    attrs = ["bus0","bus1","length"]
    candidates = pd.concat([n.lines[attrs], n.links.query('carrier=="DC"')[attrs]])\
                    .reset_index(drop=True)

    # remove bus pair duplicates regardless of order of bus0 and bus1
    h2_links = candidates[~pd.DataFrame(np.sort(candidates[['bus0', 'bus1']])).duplicated()]
    h2_links.index = h2_links.apply(lambda c: f"H2 pipeline {c.bus0}-{c.bus1}", axis=1)

    # add pipelines
    n.madd("Link",
           h2_links.index,
           bus0=h2_links.bus0.values + " H2",
           bus1=h2_links.bus1.values + " H2",
           p_min_pu=-1,
           p_nom_extendable=True,
           length=h2_links.length.values,
           capital_cost=costs.at['H2 pipeline','capital_cost']*h2_links.length,
           efficiency=costs.at['H2 pipeline','efficiency'],
           carrier="H2 pipeline")


if __name__ == "__main__":
    if 'snakemake' not in globals():
        from _helpers import mock_snakemake
        snakemake = mock_snakemake('add_extra_components', network='elec',
                                  simpl='', clusters=5)
    configure_logging(snakemake)

    n = pypsa.Network(snakemake.input.network)
    Nyears = n.snapshot_weightings.sum() / 8760.
    costs = load_costs(Nyears, tech_costs=snakemake.input.tech_costs,
                       config=snakemake.config['costs'],
                       elec_config=snakemake.config['electricity'])

    attach_storageunits(n, costs)
    attach_stores(n, costs)
    attach_hydrogen_pipelines(n, costs)

    add_nice_carrier_names(n, config=snakemake.config)

    n.export_to_netcdf(snakemake.output[0])
