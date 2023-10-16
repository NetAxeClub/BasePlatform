from driver.driver_auto_loader import driver_auto_loader, auto_driver_auto_loader

driver_map = driver_auto_loader()
auto_driver_map = auto_driver_auto_loader()


__all__ = ['driver_map', 'auto_driver_map']