import streamlit as st
import yaml
import pandas as pd
import subprocess
import os
import sqlite3
import sys
from datetime import datetime
import time

# Page Config
st.set_page_config(page_title="PriceTracker Dashboard", layout="wide")
st.title("🛒 PriceTracker Dashboard")

# --- Helper Functions ---

def load_config(path="config.yaml"):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""

def save_config(content, path="config.yaml"):
    with open(path, "w") as f:
        f.write(content)

def get_db_connection(db_path="pricetracker.db"):
    conn = sqlite3.connect(db_path)
    return conn

def run_scraper(site=None):
    """Runs the scraper as a subprocess"""
    cmd = [sys.executable, "-m", "pricetracker.cli", "run"]
    if site and site != "All":
        cmd.extend(["--site", site])
    
    # We use a placeholder to stream output
    with st.spinner(f"Running scraper for {site if site else 'all sites'}..."):
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"} # Ensure unbuffered output
        )
        
        output_container = st.empty()
        logs = []
        
        # Stream stdout associated with the process
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                logs.append(output.strip())
                # Update the container with the latest 10 logs
                output_container.code("\n".join(logs[-15:]))
        
        rc = process.poll()
        if rc == 0:
            st.success("Scraping completed successfully!")
        else:
            stderr = process.stderr.read()
            st.error(f"Scraping failed with return code {rc}")
            st.code(stderr)

# --- Tabs ---

tab1, tab2, tab3 = st.tabs(["📝 Configuration", "🚀 Runner", "📊 Results & Shopping List"])

# --- Tab 1: Config ---
with tab1:
    st.header("Configuration Editor")
    
    config_content = load_config()
    new_config_content = st.text_area(
        "Edit config.yaml", 
        value=config_content, 
        height=600
    )
    
    if st.button("Save Configuration", type="primary"):
        try:
            # Validate YAML before saving
            yaml.safe_load(new_config_content)
            save_config(new_config_content)
            st.toast("Configuration saved successfully!", icon="✅")
        except yaml.YAMLError as e:
            st.error(f"Invalid YAML format: {e}")

# --- Tab 2: Runner ---
with tab2:
    st.header("Trigger Scraper")
    
    # Parse config to get site names
    try:
        parsed_config = yaml.safe_load(config_content)
        sites = [s['name'] for s in parsed_config.get('sites', [])]
        # Sort sites for better UX
        sites.sort()
    except:
        sites = []
    
    # Options for multiselect
    # "All Enabled" passes None to the CLI, which inherently skips disabled sites
    options = ["All Enabled"] + sites
    
    selected_targets = st.multiselect(
        "Select Sites to Scrape", 
        options=options,
        default=["All Enabled"],
        help="Select 'All Enabled' to run all active sites, or select specific sites to run them individually."
    )
    
    if st.button("Run Scraper", type="primary"):
        if not selected_targets:
            st.warning("Please select at least one option.")
        else:
            # If "All Enabled" is selected, it takes precedence (or we could run it plus others, but that's redundant)
            if "All Enabled" in selected_targets:
                st.info("Running all enabled sites...")
                run_scraper(None)
            else:
                # Run each selected site sequentially
                for site in selected_targets:
                    st.write(f"### Running: {site}")
                    run_scraper(site)

# --- Tab 3: Results ---
with tab3:
    st.header("Shopping List Analysis")
    
    conn = get_db_connection()
    
    # Fetch Runs
    runs_query = "SELECT id, started_at, status, finished_at FROM runs ORDER BY id DESC"
    runs_df = pd.read_sql(runs_query, conn)
    
    if not runs_df.empty:
        # Format run display
        runs_df['display'] = runs_df.apply(lambda x: f"Run #{x['id']} - {x['started_at']} ({x['status']})", axis=1)
        
        # Multiselect for runs, default to the latest one
        selected_run_displays = st.multiselect(
            "Select Runs to Compare", 
            options=runs_df['display'],
            default=[runs_df['display'].iloc[0]]
        )
        
        if selected_run_displays:
            # Get IDs
            selected_run_ids = runs_df[runs_df['display'].isin(selected_run_displays)]['id'].tolist()
            
            # Fetch Observations for selected runs
            placeholders = ','.join(['?'] * len(selected_run_ids))
            obs_query = f"""
                SELECT 
                    run_id,
                    site_name, 
                    canonical_name, 
                    fetch_type,
                    title, 
                    price, 
                    product_url,
                    availability,
                    observed_at
                FROM observations 
                WHERE run_id IN ({placeholders})
            """
            obs_df = pd.read_sql(obs_query, conn, params=selected_run_ids)
            
            if not obs_df.empty:
                # Add friendly Run Label
                run_labels = dict(zip(runs_df['id'], runs_df['display']))
                obs_df['Run'] = obs_df['run_id'].map(run_labels)

                # --- Summary Comparison ---
                st.subheader("Total Cost Comparison")
                
                # Group by Run and Site
                summary = obs_df.groupby(['Run', 'site_name'])['price'].sum().reset_index()
                
                # Pivot for easier reading: Rows=Site, Columns=Run
                pivot_summary = summary.pivot(index='site_name', columns='Run', values='price')
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.caption("Total Cost by Site & Run")
                    st.dataframe(pivot_summary.style.format("R$ {:.2f}"), width='stretch')
                
                with col2:
                    st.caption("Visual Comparison")
                    st.bar_chart(summary, x='site_name', y='price', color='Run', stack=False)

                # --- Product Price Comparison Chart ---
                st.divider()
                st.subheader("Product Price Comparison Chart")
                st.caption("Compare prices for products available on multiple sites (only showing products found in 2+ sites)")
                
                # Find products that appear on multiple sites
                product_site_counts = obs_df.groupby('canonical_name')['site_name'].nunique().reset_index()
                product_site_counts.columns = ['canonical_name', 'site_count']
                multi_site_products = product_site_counts[product_site_counts['site_count'] >= 2]['canonical_name'].tolist()
                
                if multi_site_products:
                    # Filter observations to only include multi-site products
                    multi_site_obs = obs_df[obs_df['canonical_name'].isin(multi_site_products)].copy()
                    
                    # Product filter
                    selected_chart_products = st.multiselect(
                        "Select Products to Compare", 
                        options=multi_site_products, 
                        default=multi_site_products[:5] if len(multi_site_products) > 5 else multi_site_products,
                        key="chart_product_filter"
                    )
                    
                    if selected_chart_products:
                        filtered_chart_data = multi_site_obs[multi_site_obs['canonical_name'].isin(selected_chart_products)]
                        
                        # Create a more readable format for the chart
                        # Group by product and site, taking the first price (in case of duplicates)
                        chart_data = filtered_chart_data.groupby(['canonical_name', 'site_name'])['price'].first().reset_index()
                        
                        # Create the grouped bar chart
                        st.bar_chart(chart_data, x='canonical_name', y='price', color='site_name', stack=False)
                        
                        # Show summary statistics
                        st.caption("💡 **Tip**: This chart helps identify which site offers the best price for each product.")
                        
                        # Optional: Show a table with the data
                        with st.expander("View Detailed Price Data"):
                            pivot_chart = chart_data.pivot(index='canonical_name', columns='site_name', values='price')
                            st.dataframe(pivot_chart.style.format("R$ {:.2f}"), width='stretch')
                    else:
                        st.info("Please select at least one product to display in the chart.")
                else:
                    st.info("No products found on multiple sites. Products must appear on at least 2 sites to enable comparison.")

                # --- Detailed View ---
                st.divider()
                st.subheader("Detailed Observations")
                
                # Filter by site in view
                all_sites = obs_df['site_name'].unique()
                filter_site = st.multiselect("Filter by Site", options=all_sites, default=all_sites)
                
                filtered_df = obs_df[obs_df['site_name'].isin(filter_site)]
                
                st.dataframe(
                    filtered_df,
                    column_config={
                        "product_url": st.column_config.LinkColumn("Product Link"),
                        "price": st.column_config.NumberColumn("Price", format="R$ %.2f"),
                        "observed_at": st.column_config.DatetimeColumn("Time", format="D MMM, HH:mm"),
                        "fetch_type": st.column_config.Column("Fetch Type", width="small"),
                    },
                    width='stretch',
                    hide_index=True
                )
                
                # --- Product Comparison ---
                st.divider()
                st.subheader("Product Price Comparison")
                st.caption("Compare prices for specific products across different Sites and Runs.")

                # Pivot: Rows=(Product, Site), Cols=Run, Val=Price
                # We use pivot_table to handle duplicates if any (though duplicates shouldn't exist ideally)
                comparison_df = obs_df.pivot_table(
                    index=['canonical_name', 'title', 'site_name'], 
                    columns='Run', 
                    values='price',
                    aggfunc='first'
                )
                
                # Optional Filter
                all_products = obs_df['canonical_name'].unique()
                selected_products = st.multiselect("Filter by Product", options=all_products, default=all_products)
                
                # Filter the pivot table based on selection
                # Since index is MultiIndex, we filter level 0
                filtered_comparison = comparison_df[comparison_df.index.get_level_values('canonical_name').isin(selected_products)]
                
                st.dataframe(filtered_comparison.style.format("R$ {:.2f}"), width='stretch')

            else:
                st.info("No observations found for the selected runs.")
        else:
            st.info("Please select at least one run to view results.")
    else:
        st.warning("No runs found in the database.")
    
    conn.close()
