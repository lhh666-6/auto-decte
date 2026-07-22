import { useParams } from "react-router-dom";

import { BambooRecordDetailPage } from "./bamboo/BambooRecordDetailPage";
import { BambooTaskListPage } from "./bamboo/BambooTaskListPage";

export function MobileBambooProcessPage() {
  const { recordId } = useParams<{ recordId: string }>();
  return recordId
    ? <BambooRecordDetailPage recordId={recordId} />
    : <BambooTaskListPage />;
}
