with cte_first_year as
  (
  select
    clients.client_id,
    clients.company_name,
    clients.salesforce_account_id,
    sfdc_account.segment_c as segment,

    sfdc_account.industry_classification_c as industry,
    sfdc_account.zisf_zoom_info_industry_c as industry_zoominfo,
    sfdc_account.dnb_naics_code_c as dnb_naics,
    sfdc_account.dnb_import_export_status_c as import_or_exporter,
    sfdc_account.flexport_office_c as flexport_territory,
    sfdc_account.lead_source_c as lead_source,
    sfdc_account.wholesale_partners_c as wholesale_partners,

    sfdc_account.total_annual_volume_c as total_annual_volume,
    sfdc_account.total_annual_fcl_volume_c as total_annual_fcl_volume,
    sfdc_account.total_annual_air_volume_c as total_annual_air_volume,
    sfdc_account.total_annual_lcl_volume_c as total_annual_lcl_volume,

    sfdc_account.shipment_count_piers_c as piers_shipment_count,
    sfdc_account.teus_piers_c as piers_total_teu,
    sfdc_account.teus_piers_c - coalesce(sfdc_account.bco_teus_piers_c,0) as piers_nvo_teu,

    clients.first_shipment_accepted_at,
    date_trunc('month', clients.first_shipment_accepted_at) as first_shipment_month,
    date_trunc('quarter', clients.first_shipment_accepted_at) as first_shipment_quarter,
    count(shipments.shipment_id) as fy_shipments,
    sum(case when prep_shipment_balances.complete_billing = true then prep_shipment_balances.net_revenue_usd end) as actual_net_revenue,
    sum(case when prep_shipment_balances.complete_billing = true then prep_shipment_balances.revenue_usd end) as invoice_total_revenue,
    sum(case when prep_shipment_balances.complete_billing = true then prep_shipment_balances.billed_total_sanz_passthrough_amount_usd end) as bill_total_sans_passthrough
  from analytics.legacy.prep_clients_entity as clients
    join analytics.sfdc.account as sfdc_account
      on sfdc_account.id = clients.salesforce_account_id
    join analytics.legacy.bi_shipments as shipments
      on shipments.client_id = clients.client_id
      and shipments.is_live_shipment
      and shipments.shipment_accepted_at between clients.first_shipment_accepted_at
        and dateadd(day, 365, clients.first_shipment_accepted_at)
    join analytics.legacy.prep_shipment_balances as prep_shipment_balances
      on prep_shipment_balances.shipment_id = shipments.shipment_id
  where clients.first_shipment_accepted_at >= '2017-01-01'
  group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21
  )

  , cte_piers_match as
  (
  select
    cte_first_year.salesforce_account_id,
    count(imports.import_detail_bol_sk) as shipment_count,
    sum(case
          when left(imports.bill_number, 4) not in ('MSCU','HLCU','MAEU','CMDU','EGLV','COSU','APLU','OOLU','KKLU','HDMU','NYKS','YMLU','HJSC','MOLU','ZIMU','SUDU','UASU','CHNJ','SMLU','PABV','WHLC','ACLU','CHHK','HLUS','ANLC','MEDU','ONEY')
            then coalesce(imports.total_teus,0)
          else 0
        end) as raw_piers_nvo_teu,
    sum(coalesce(imports.total_teus,0)) as raw_piers_total_teu,
    coalesce(raw_piers_nvo_teu / nullif(raw_piers_total_teu,0),0) as raw_piers_pct_nvo,
    sum(coalesce(imports.total_estimated_value,0)) as raw_piers_estimated_commodity_value
  from cte_first_year
    join analytics.legacy.piers_enigma_sfdc_matched_final as match
      on match.sfdc_id = cte_first_year.salesforce_account_id
      and match.is_in_sfdc = true
    join analytics.piers.import_details as imports
      on imports.import_detail_bol_sk = match.import_detail_bol_sk
      and imports.shipping_detail_arrival_date between dateadd(days, -365, cte_first_year.first_shipment_accepted_at) and cte_first_year.first_shipment_accepted_at
  group by 1
  )

  , cte_final as
  (
  select
    cte_first_year.*
    , cte_piers_match.raw_piers_total_teu
    , cte_piers_match.raw_piers_nvo_teu
    , cte_piers_match.raw_piers_pct_nvo
    , cte_piers_match.raw_piers_estimated_commodity_value
  from cte_first_year
    left join cte_piers_match
      on cte_piers_match.salesforce_account_id = cte_first_year.salesforce_account_id
  )

select
  client_id,
  company_name,
  salesforce_account_id,
  segment,
  industry,
  industry_zoominfo,
  dnb_naics,
  import_or_exporter,
  flexport_territory,
  lead_source,
  wholesale_partners,
  total_annual_volume,
  total_annual_fcl_volume,
  total_annual_air_volume,
  total_annual_lcl_volume,
  piers_shipment_count,
  piers_total_teu,
  piers_nvo_teu,
  first_shipment_accepted_at,
  first_shipment_month,
  first_shipment_quarter,
  fy_shipments,
  actual_net_revenue,
  invoice_total_revenue,
  bill_total_sans_passthrough,
  raw_piers_total_teu,
  raw_piers_nvo_teu,
  raw_piers_pct_nvo,
  raw_piers_estimated_commodity_value
from cte_final
