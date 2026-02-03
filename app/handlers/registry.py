"""
Handler registry for simulation and report handlers.

This module provides the plugin system for registering custom simulation
and report handlers. The service is agnostic to specific simulation/report
types - handlers are registered at startup to provide the actual implementation.

Example usage:

    # Define a custom simulation handler
    class MonteCarloHandler(SimulationHandler):
        def execute(self, job_id, simulation_type, parameters, progress_callback):
            # Run Monte Carlo simulation
            result = run_monte_carlo(parameters)
            return result
    
    # Register the handler
    SimulationHandlerRegistry.register("monte_carlo", MonteCarloHandler())
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SimulationHandler(ABC):
    """
    Abstract base class for simulation handlers.
    
    Implement this class to add support for a specific simulation type.
    """

    @abstractmethod
    def execute(
        self,
        job_id: str,
        simulation_type: str,
        parameters: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> dict[str, Any]:
        """
        Execute the simulation.
        
        Args:
            job_id: Unique job identifier
            simulation_type: Type of simulation
            parameters: Simulation parameters
            progress_callback: Optional callback to report progress (0.0 to 1.0)
            
        Returns:
            Simulation result as a dictionary
        """
        pass

    def validate_parameters(self, parameters: dict[str, Any]) -> bool:
        """
        Validate simulation parameters.
        
        Override this method to add parameter validation.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        return True


class ReportHandler(ABC):
    """
    Abstract base class for report handlers.
    
    Implement this class to add support for a specific report type.
    """

    @abstractmethod
    def generate(
        self,
        report_id: str,
        report_type: str,
        output_format: str,
        parameters: dict[str, Any],
        simulation_results: list[dict[str, Any]],
    ) -> tuple[bytes, str, str]:
        """
        Generate the report.
        
        Args:
            report_id: Unique report identifier
            report_type: Type of report
            output_format: Desired output format (PDF, HTML, JSON, etc.)
            parameters: Report generation parameters
            simulation_results: List of simulation results to include
            
        Returns:
            Tuple of (file_content, content_type, filename)
        """
        pass

    def validate_parameters(self, parameters: dict[str, Any]) -> bool:
        """
        Validate report parameters.
        
        Override this method to add parameter validation.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        return True


class SimulationHandlerRegistry:
    """
    Registry for simulation handlers.
    
    Handlers are registered by simulation type and retrieved when
    processing simulation jobs.
    """

    _handlers: dict[str, SimulationHandler] = {}

    @classmethod
    def register(cls, simulation_type: str, handler: SimulationHandler) -> None:
        """
        Register a handler for a simulation type.
        
        Args:
            simulation_type: Type identifier (e.g., "monte_carlo")
            handler: SimulationHandler instance
        """
        cls._handlers[simulation_type] = handler
        logger.info(f"Registered simulation handler for type: {simulation_type}")

    @classmethod
    def unregister(cls, simulation_type: str) -> None:
        """
        Unregister a handler.
        
        Args:
            simulation_type: Type identifier to unregister
        """
        if simulation_type in cls._handlers:
            del cls._handlers[simulation_type]
            logger.info(f"Unregistered simulation handler for type: {simulation_type}")

    @classmethod
    def get_handler(cls, simulation_type: str) -> Optional[SimulationHandler]:
        """
        Get the handler for a simulation type.
        
        Args:
            simulation_type: Type identifier
            
        Returns:
            SimulationHandler instance or None if not registered
        """
        return cls._handlers.get(simulation_type)

    @classmethod
    def list_handlers(cls) -> list[str]:
        """
        List all registered simulation types.
        
        Returns:
            List of registered simulation type identifiers
        """
        return list(cls._handlers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers (useful for testing)."""
        cls._handlers.clear()


class ReportHandlerRegistry:
    """
    Registry for report handlers.
    
    Handlers are registered by report type and retrieved when
    generating reports.
    """

    _handlers: dict[str, ReportHandler] = {}

    @classmethod
    def register(cls, report_type: str, handler: ReportHandler) -> None:
        """
        Register a handler for a report type.
        
        Args:
            report_type: Type identifier (e.g., "summary")
            handler: ReportHandler instance
        """
        cls._handlers[report_type] = handler
        logger.info(f"Registered report handler for type: {report_type}")

    @classmethod
    def unregister(cls, report_type: str) -> None:
        """
        Unregister a handler.
        
        Args:
            report_type: Type identifier to unregister
        """
        if report_type in cls._handlers:
            del cls._handlers[report_type]
            logger.info(f"Unregistered report handler for type: {report_type}")

    @classmethod
    def get_handler(cls, report_type: str) -> Optional[ReportHandler]:
        """
        Get the handler for a report type.
        
        Args:
            report_type: Type identifier
            
        Returns:
            ReportHandler instance or None if not registered
        """
        return cls._handlers.get(report_type)

    @classmethod
    def list_handlers(cls) -> list[str]:
        """
        List all registered report types.
        
        Returns:
            List of registered report type identifiers
        """
        return list(cls._handlers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers (useful for testing)."""
        cls._handlers.clear()
