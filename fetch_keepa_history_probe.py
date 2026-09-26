import fetch_keepa


if __name__ == "__main__":
    from research_hourly import BudgetPause
    try:fetch_keepa.main()
    except BudgetPause:print('Shared hourly token limit reached; remaining price scans wait for the next run.')
