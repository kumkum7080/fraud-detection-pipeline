import operator
from sqlalchemy.orm import Session
from backend.app.models import Rule, Transaction, Alert
from backend.app.config import settings

# Operator mapping for safe evaluation
OPERATORS = {
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne
}

class RulesEngine:
    @staticmethod
    def evaluate_rules(
        db: Session, 
        amount: float, 
        rolling_avg: float, 
        velocity_1h: int, 
        zip_mismatch: int,
        deviation_ratio: float
    ) -> float:
        """
        Fetches active static fraud rules from MySQL, evaluates them,
        and returns the aggregate risk modifier sum.
        """
        # Fetch active rules
        active_rules = db.query(Rule).filter(Rule.is_active == True).all()
        
        # Build features context dict
        context = {
            'amount': amount,
            'rolling_avg_amount': rolling_avg,
            'velocity_1h': velocity_1h,
            'zip_mismatch': zip_mismatch,
            'amount_deviation_ratio': deviation_ratio
        }
        
        rule_modifier = 0.0
        
        for rule in active_rules:
            # Safely fetch field value
            val = context.get(rule.field_name)
            if val is None:
                continue
                
            # Safely fetch comparison operator
            op_func = OPERATORS.get(rule.operator)
            if not op_func:
                continue
                
            try:
                # Evaluate e.g., amount > 5000
                if op_func(val, rule.threshold_value):
                    rule_modifier += rule.risk_modifier
            except Exception as e:
                print(f"[WARNING] Rules Engine: Error evaluating rule '{rule.name}': {e}")
                
        return rule_modifier

    @staticmethod
    def evaluate_and_score(
        db: Session,
        amount: float,
        rolling_avg: float,
        velocity_1h: int,
        zip_mismatch: int,
        ml_predicted_anomaly: int,
        ml_risk_score: float
    ) -> tuple[float, bool]:
        """
        Combines the Machine Learning anomaly risk score with the static database rule modifiers
        to return the final risk score and whether the transaction should trigger an Alert.
        """
        deviation_ratio = round(amount / max(rolling_avg, 0.01), 2)
        
        # Get score modifiers from rule checks
        rule_modifier = RulesEngine.evaluate_rules(
            db=db,
            amount=amount,
            rolling_avg=rolling_avg,
            velocity_1h=velocity_1h,
            zip_mismatch=zip_mismatch,
            deviation_ratio=deviation_ratio
        )
        
        # Combine: final score is ML risk score + rule modifier
        # Clamp between 0.0% and 100.0%
        final_score = round(max(0.0, min(100.0, ml_risk_score + rule_modifier)), 1)
        
        # Generate alert flag if combined score exceeds configured system threshold
        should_alert = final_score >= settings.ALERT_THRESHOLD
        
        return final_score, should_alert
