/** Reusable signature card — displays electronic signature as a business card */

export interface SignatureInfo {
  actor_name: string;
  employee_code: string;
  role_label: string;
  factory_name: string;
  signed_at: string;
}

export function SignatureCard({ signature, label }: { signature: SignatureInfo; label?: string }) {
  return (
    <div className="signature-card">
      <h4 className="signature-card-title">{label || "电子签字"}</h4>
      <div className="signature-card-body">
        <div className="signature-card-field">
          <span className="signature-card-lbl">签字人</span>
          <span className="signature-card-val">{signature.actor_name}</span>
        </div>
        <div className="signature-card-field">
          <span className="signature-card-lbl">工号</span>
          <span className="signature-card-val">{signature.employee_code}</span>
        </div>
        <div className="signature-card-field">
          <span className="signature-card-lbl">岗位</span>
          <span className="signature-card-val">{signature.role_label}</span>
        </div>
        <div className="signature-card-field">
          <span className="signature-card-lbl">工厂</span>
          <span className="signature-card-val">{signature.factory_name}</span>
        </div>
        <div className="signature-card-field">
          <span className="signature-card-lbl">签字时间</span>
          <span className="signature-card-val">{signature.signed_at}</span>
        </div>
      </div>
    </div>
  );
}
